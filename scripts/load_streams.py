
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple

from brownie import chain
from pony.orm import db_session
from tqdm import tqdm

from yearn.entities import Stream, StreamedFunds, create_views
from yearn.treasury.constants import BUYER
from yearn.treasury.streams import YearnStreams
from yearn.utils import dates_between

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

    process_streams()

@db_session
def all_other_dai_streams():
    return [s for s in streams.dai_streams() if s.to_address.address != BUYER]

@db_session
def process_stream(stream_id: str, date: datetime):
    return StreamedFunds.get_or_create_entity(date = date, stream = Stream[stream_id])

def get_start_and_end(stream: Stream) -> Tuple[datetime, datetime]:
    start_timestamp = datetime.fromtimestamp(chain[stream.start_block].timestamp)
    end_timestamp = datetime.fromtimestamp(chain[stream.end_block].timestamp) if stream.end_block else datetime.utcnow()
    return start_timestamp, end_timestamp

def process_streams():
    datapoints = [(stream, date) for stream in streams.streams(include_inactive=True) for date in dates_between(*get_start_and_end(stream))]
    for stream, date in tqdm(datapoints):
        process_stream(stream.stream_id, date)
