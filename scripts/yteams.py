
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from typing import List

import a_sync
from eth_portfolio import _shitcoins
from eth_portfolio._ydb.token_transfers import InboundTokenTransfers
from y import get_block_at_timestamp

_shitcoins.SHITCOINS[1].add("0x1C67D8F07D7ef2d637E61eD3FBc3fa9AAF7A6267")


yteam_split_contracts = {
    "v3": "0x33333333D5eFb92f19a5F94a43456b3cec2797AE",
    "dinobots": "0x2C01B4AD51a67E2d8F02208F54dF9aC4c0B778B6",
    "ylockers": "0x4444AAAACDBa5580282365e25b16309Bd770ce4a",
    "corn + yaudit": "0xF6411852b105042bb8bbc6Dd50C0e8F30Af63337",
    "yeth": "0xeEEEEeeeEe274C3CCe13f77C85d8eBd9F7fd4479",
}

name_mapping = {v:k for k, v in yteam_split_contracts.items()}

logging.basicConfig(level=logging.INFO)

start = datetime(2023, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
now = datetime.now(timezone.utc)

dts: List[datetime] = []
next = start
while next <= now:
    dts.append(next - timedelta(seconds=1))
    if next.month == 12:
        next = datetime(year=next.year+1, month=1, day=1, tzinfo=timezone.utc)
    else:
        next = datetime(next.year, next.month+1, 1, tzinfo=timezone.utc)

def main():
    asyncio.get_event_loop().run_until_complete(_main())

async def _main():
    for dt, data in zip(dts, await a_sync.gather(
        *[a_sync.gather({label: total(wallet, dt) for label, wallet in yteam_split_contracts.items()}) for dt in dts]
    )):
        print(dt)
        print(data)

@lru_cache(maxsize=None)
def transfers_for(wallet: str) -> InboundTokenTransfers:
    return InboundTokenTransfers(wallet, 0, load_prices=True)

async def sum_inbound_transfers(wallet: str, timestamp: datetime) -> Decimal:
    block = await get_block_at_timestamp(timestamp)
    total = Decimal(0)
    async for transfer in transfers_for(wallet).yield_thru_block(block):
        transfer = await transfer
        if transfer is None:
            # failed to decode, probably shitcoin
            continue
        if not transfer.value:
            # zero value transfer
            continue
        if transfer.value and transfer.price:
            total += transfer.value * transfer.price
        elif not any([transfer.value, transfer.price]):
            # zero value transfer, skip
            pass
        else:
            print('BAD:')
            print(transfer)
    print(f'{name_mapping[wallet]} inbound thru {timestamp}: {total}')
    return total

async def sum_expenditures(wallet: str, timestamp: datetime) -> Decimal:
    # TODO
    exp = Decimal()
    print(f'{name_mapping[wallet]} expenditures thru {timestamp}: {exp}')
    return exp

async def total(wallet: str, timestamp: datetime) -> Decimal:
    rev, exp = await asyncio.gather(sum_inbound_transfers(wallet, timestamp), sum_expenditures(wallet, timestamp))
    t = rev - exp
    print(f'{name_mapping[wallet]} total thru {timestamp}: {t}')
    return t
