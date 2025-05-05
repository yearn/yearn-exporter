
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, List, Optional, Tuple

from async_lru import alru_cache
from brownie import chain
from dank_mids.helpers import lru_cache_lite
from eth_portfolio._cache import cache_to_disk
from pony.orm import db_session, select
from tqdm.asyncio import tqdm_asyncio
from y import Contract, Network, get_price
from y.constants import CHAINID
from y.time import closest_block_after_timestamp_async

from yearn.cache import memory
from yearn.constants import YCHAD_MULTISIG, YFI
from yearn.entities import Stream, StreamedFunds, TxGroup
from yearn.events import decode_logs, get_logs_asap
from yearn.outputs.postgres.utils import token_dbid
from yearn.treasury.constants import BUYER
from yearn.utils import dates_generator, threads


ONE_DAY = 60 * 60 * 24

dai = "0x6B175474E89094C44Da98b954EedeAC495271d0F"

if CHAINID == Network.Mainnet:
    streams_dai = Contract('0x60c7B0c5B3a4Dc8C690b074727a17fF7aA287Ff2')
    streams_yfi = Contract('0xf3764eC89B1ad20A31ed633b1466363FAc1741c4')

logger = logging.getLogger(__name__)

class YearnStreams:
    def __init__(self):
        assert CHAINID == 1
        self.stream_contracts = [streams_dai, streams_yfi]
        self.skipped_events = ["PayerDeposit", "PayerWithdraw", "Withdraw"]
        self.handled_events = ["StreamCreated", "StreamCreatedWithReason", "StreamModified", "StreamPaused", "StreamCancelled"]
        self.get_streams()
            
    def __getitem__(self, key: str):
        if isinstance(key, bytes):
            key = key.hex()
        return Stream[key]

    def streams_for_recipient(self, recipient: str, at_block: Optional[int] = None) -> List[Stream]:
        if at_block is None:
            return list(select(s for s in Stream if s.to_address.address == recipient))
        return list(select(s for s in Stream if s.to_address.address == recipient and (s.end_block is None or at_block <= s.end_block)))
    
    def streams_for_token(self, token: str, include_inactive: bool = False) -> List[Stream]:
        streams = list(select(s for s in Stream if s.token.token_id == token_dbid(token)))
        if include_inactive is False:
            streams = [s for s in streams if s.is_alive]
        return streams

    def buyback_streams(self, include_inactive: bool = False) -> List[Stream]:
        streams = self.streams_for_recipient(BUYER)
        if include_inactive is False:
            streams = [s for s in streams if s.is_alive]
        return streams
    
    @db_session
    def dai_streams(self, include_inactive: bool = False) -> List[Stream]:
        return self.streams_for_token(dai, include_inactive=include_inactive)

    @db_session
    def yfi_streams(self, include_inactive: bool = False) -> List[Stream]:
        return self.streams_for_token(YFI, include_inactive=include_inactive)
    
    @db_session
    def streams(self, include_inactive: bool = False):
        if include_inactive is True:
            return list(select(s for s in Stream))
        return list(select(s for s in Stream if s.is_alive))

    @db_session
    def get_streams(self):
        for stream_contract in self.stream_contracts:
            logs = decode_logs(get_logs_asap([stream_contract.address]))

            for k in logs.keys():
                if k not in self.handled_events and k not in self.skipped_events:
                    raise NotImplementedError(f"We need to build handling for {k} events.")

            for log in logs['StreamCreated']:
                from_address, *_ = log.values()
                if from_address != YCHAD_MULTISIG:
                    continue
                Stream.get_or_create_entity(log)
            
            if "StreamCreatedWithReason" in logs:
                for log in logs['StreamCreatedWithReason']:
                    from_address, *_ = log.values()
                    if from_address != YCHAD_MULTISIG:
                        continue
                    Stream.get_or_create_entity(log)
            
            for log in logs['StreamModified']:
                from_address, _, _, old_stream_id, *_ = log.values()
                if from_address != YCHAD_MULTISIG:
                    continue
                self[old_stream_id].stop_stream(log.block_number)
                Stream.get_or_create_entity(log)

            if 'StreamPaused' in logs:
                for log in logs['StreamPaused']:
                    from_address, *_, stream_id = log.values()
                    if from_address != YCHAD_MULTISIG:
                        continue
                    self[stream_id].pause(log.block_number)
            
            if 'StreamCancelled' in logs:
                for log in logs['StreamCancelled']:
                    from_address, *_, stream_id = log.values()
                    if from_address != YCHAD_MULTISIG:
                        continue
                    self[stream_id].stop_stream(log.block_number)

        team_payments_txgroup = TxGroup.get(name = "Team Payments")
        for stream in self.yfi_streams(include_inactive=True):
            for stream in self.streams_for_recipient(stream.to_address.address):
                if stream.txgroup is None:
                    stream.txgroup = team_payments_txgroup

if CHAINID == Network.Mainnet:
    streams = YearnStreams()

@db_session
def all_other_dai_streams():
    return [s for s in streams.dai_streams() if s.to_address.address != BUYER]

@alru_cache
async def get_stream_contract(stream_id: str) -> Contract:
    address = await threads.run(_get_stream_contract, stream_id)
    return await Contract.coroutine(address)

@db_session
def get_start_date(stream_id: str) -> date:
    return Stream[stream_id].start_date

@db_session
def is_closed(stream_id: str) -> bool:
    return bool(StreamedFunds.get(stream=Stream[stream_id], is_last_day=True))

@cache_to_disk
async def start_timestamp(stream_id: str, block: Optional[int] = None) -> int:
    contract = await get_stream_contract(stream_id)
    return int(await contract.streamToStart.coroutine(f'0x{stream_id}', block_identifier=block))


@alru_cache(maxsize=None)
@cache_to_disk
async def closest_block_after_timestamp(ts: int) -> int:
    return await closest_block_after_timestamp_async(ts)


async def process_stream_for_date(stream_id: str, date: datetime) -> Optional[StreamedFunds]:
    if entity := await threads.run(StreamedFunds.get_entity, stream_id, date):
        return entity
    
    stream_token = _get_token_for_stream(stream_id)
    check_at = date + timedelta(days=1) - timedelta(seconds=1)
    block = await closest_block_after_timestamp(int(check_at.timestamp()))
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
    logger.debug("active for %s seconds on %s", seconds_active_today, date.date())
    if is_last_day:
        logger.debug('is last day')
    
    price = Decimal(await price_fut)
    return await threads.run(StreamedFunds.create_entity, stream_id, date, price, seconds_active_today, is_last_day)

@memory.cache
def get_ts(block: int) -> datetime:
    return datetime.fromtimestamp(chain[block].timestamp)

def get_start_and_end(stream: Stream) -> Tuple[datetime, datetime]:
    start_timestamp = get_ts(stream.start_block)
    end_timestamp = get_ts(stream.end_block) if stream.end_block else datetime.now(timezone.utc)
    return start_timestamp, end_timestamp

async def process_stream(stream, run_forever: bool = False) -> None:
    # NOTE: We need to go one-by-one for the math to be right
    async for date in dates_generator(*get_start_and_end(stream), stop_at_today=not run_forever):
        if await process_stream_for_date(stream.stream_id, date) is None:
            return
    
async def process_streams(run_forever: bool = False):
    await tqdm_asyncio.gather(*[process_stream(stream, run_forever=run_forever) for stream in streams.streams(include_inactive=True)], desc='Loading streams')


@db_session
def _get_stream_contract(stream_id: str) -> str:
    return Stream[stream_id].contract.address

@lru_cache_lite
@db_session
def _get_token_for_stream(stream_id):
    return Stream[stream_id].token.address.address


# TODO: Fit this better into the rest of the exporter so it runs in tandem with treasury txs exporter
@db_session
def _get_coro() -> Awaitable[None]:
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

    return process_streams()