
import asyncio
import typing
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Tuple, Optional

from a_sync import AsyncThreadPoolExecutor
import logging
from async_lru import alru_cache
from brownie import chain
from pony.orm import db_session
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio
from y import Contract, get_price
from y.time import closest_block_after_timestamp_async

from yearn.entities import Stream, StreamedFunds, create_views
from yearn.treasury.constants import BUYER
from yearn.treasury.streams import YearnStreams
from yearn.utils import dates_generator

logger = logging.getLogger(__name__)

create_views()
streams = YearnStreams()

# TODO: Fit this better into the rest of the exporter so it runs in tandem with treasury txs exporter

@db_session
def main():
    #print('buybacks active stream(s)')
    for stream in streams.buyback_streams():
        #stream.print()
        pass

    team_dai_streams = [stream for stream in all_other_dai_streams() if int(stream.amount_per_second) == 385802469135802432]

    #print(f'{len(team_dai_streams)} team dai streams')
    total_rate = 0
    for i, stream in enumerate(team_dai_streams):
        total_rate += stream.amount_per_second
    total_rate /= stream.scale
    #print(f'team dai per second: {total_rate}')
    #print(f'team dai per day: {total_rate * 60 * 60 * 24}')

    v3_multisig_i_think = "0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7"
    v3_dai_streams = [stream for stream in all_other_dai_streams() if stream.to_address.address == v3_multisig_i_think]

    print(f'{len(v3_dai_streams)} v3 dai streams')
    total_rate = 0
    for i, stream in enumerate(v3_dai_streams):
        total_rate += stream.amount_per_second
    total_rate /= stream.scale
    print(f'v3 dai per second: {total_rate}')
    print(f'v3 dai per day: {total_rate * 60 * 60 * 24}')

    misc_dai_streams = [stream for stream in all_other_dai_streams() if stream not in team_dai_streams and stream.to_address.address != v3_multisig_i_think]

    print('all other active streams')
    total_rate = 0
    for i, stream in enumerate(misc_dai_streams):
        print(f'stream {i}')
        total_rate += stream.amount_per_second
        #print(stream.amount_per_second)
        stream.print()
    total_rate /= stream.scale
    print(f'all other streams dai per second: {total_rate}')
    print(f'all other streams dai per day: {total_rate * 60 * 60 * 24}')

    yfi_streams = streams.yfi_streams()

    normal_daily_rate = Decimal(5.2950767511632e-07) * 60 * 60 * 24
    print(f'{len(yfi_streams)} active yfi streams')
    total_rate = 0
    for i, stream in enumerate(yfi_streams):
        rate = stream.amount_per_second
        total_rate += rate
        if rate != 5.2950767511632e-07:
            print(f'stream {i}')
            stream.print()
            print(f'normal YFI per day: {normal_daily_rate}')
            daily_rate = rate * 60 * 60 * 24
            daily_difference = daily_rate - normal_daily_rate
            print(f'daily difference: {daily_difference} YFI')
            print(f'monthly difference: {daily_difference * 30} YFI')
            print(f'recipient: {stream.to_address.address}')

    print('')
    print(f'total yfi per second: {total_rate}')
    print(f'total yfi per day: {total_rate * 60 * 60 * 24}')

    asyncio.get_event_loop().run_until_complete(process_streams())

@db_session
def all_other_dai_streams():
    return [s for s in streams.dai_streams() if s.to_address.address != BUYER]


threads = AsyncThreadPoolExecutor(8)

@lru_cache
@db_session
def _get_token_for_stream(stream_id):
    return Stream[stream_id].token.address.address

@db_session
def _get_stream_contract(stream_id: str) -> str:
    return Stream[stream_id].contract.address

@db_session
def get_start_date(stream_id: str) -> date:
    return Stream[stream_id].start_date

@db_session
def is_closed(stream_id: str) -> bool:
    return bool(StreamedFunds.get(stream=Stream[stream_id], is_last_day=True))

@alru_cache
async def get_stream_contract(stream_id: str) -> Contract:
    address = await threads.run(_get_stream_contract, stream_id)
    return await Contract.coroutine(address)

async def start_timestamp(stream_id: str, block: typing.Optional[int] = None) -> int:
    contract = await get_stream_contract(stream_id)
    return int(await contract.streamToStart.coroutine(f'0x{stream_id}', block_identifier=block))

ONE_DAY = 60 * 60 * 24

async def process_stream_for_date(stream_id: str, date: datetime) -> Optional[StreamedFunds]:
    if entity := await threads.run(StreamedFunds.get_entity, stream_id, date):
        return entity
    
    stream_token = _get_token_for_stream(stream_id)
    check_at = date + timedelta(days=1) - timedelta(seconds=1)
    block = await closest_block_after_timestamp_async(int(check_at.timestamp()))
    price_fut = asyncio.create_task(get_price(stream_token, block, sync=False))
    _start_timestamp = await start_timestamp(stream_id, block)
    if _start_timestamp == 0:
        # If the stream was already closed, we can return `None`.
        if await threads.run(is_closed, stream_id):
            price_fut.cancel()
            return None
        
        while _start_timestamp == 0:
            # is active last block?
            block -= 1
            _start_timestamp = await start_timestamp(stream_id, block)

        block_datetime = datetime.fromtimestamp(chain[block].timestamp)
        assert block_datetime.date() == date.date()
        seconds_active = (check_at - block_datetime).seconds
        is_last_day = True
    else:
        seconds_active = int(check_at.timestamp()) - _start_timestamp
        is_last_day = False
    
    # How many seconds was the stream active on `date`?
    seconds_active_today = seconds_active if seconds_active < ONE_DAY else ONE_DAY
    if seconds_active_today < ONE_DAY and not is_last_day:
        if date.date() == await threads.run(get_start_date, stream_id):
            logger.debug('stream started today, partial day accepted')
        else:
            seconds_active_today = ONE_DAY
    logger.debug(F"active for {seconds_active_today} seconds on {date.date()}")
    if is_last_day:
        logger.debug('is last day')
    
    price = Decimal(await price_fut)
    return await threads.run(StreamedFunds.create_entity, stream_id, date, price, seconds_active_today, is_last_day)

def get_start_and_end(stream: Stream) -> Tuple[datetime, datetime]:
    start_timestamp = datetime.fromtimestamp(chain[stream.start_block].timestamp)
    end_timestamp = datetime.fromtimestamp(chain[stream.end_block].timestamp) if stream.end_block else datetime.utcnow()
    return start_timestamp, end_timestamp

async def process_stream(stream, run_forever: bool = False) -> None:
    # NOTE: We need to go one-by-one for the math to be right
    async for date in dates_generator(*get_start_and_end(stream), stop_at_today=not run_forever):
        if await process_stream_for_date(stream.stream_id, date) is None:
            return
    
async def process_streams(run_forever: bool = False):
    await tqdm_asyncio.gather(*[process_stream(stream, run_forever=run_forever) for stream in streams.streams(include_inactive=True)], desc='Loading streams')
