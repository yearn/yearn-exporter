import logging
import time
from datetime import datetime, timedelta, timezone
from itertools import count

from yearn.entities import Block, Snapshot, db_session
from yearn.utils import closest_block_after_timestamp, get_block_timestamp
from yearn.yearn import Yearn

logger = logging.getLogger("yearn.historical_tvl")


def generate_snapshot_blocks(start, interval):
    for i in count():
        while start + i * interval > datetime.now().astimezone(timezone.utc):
            time.sleep(60)

        timestamp = start + i * interval
        block = closest_block_after_timestamp(timestamp.timestamp())
        yield block, timestamp


def main():
    yearn = Yearn()
    start = datetime(2020, 2, 12, tzinfo=timezone.utc)  # first iearn deployment
    interval = timedelta(days=1)
    for block, snapshot_ts in generate_snapshot_blocks(start, interval):
        with db_session:
            if Block.get(block=block):
                continue

            assets = yearn.total_value_at(block)
            block_ts = datetime.fromtimestamp(get_block_timestamp(block)).astimezone(timezone.utc)
            new_block = Block(block=block, timestamp=block_ts, snapshot=snapshot_ts)

            for product in assets:
                for name in assets[product]:
                    Snapshot(block=new_block, product=product, name=name, assets=assets[product][name])

            total = sum(sum(x.values()) for x in assets.values())
            logger.info(f"%s block %d tvl %.0f", snapshot_ts.date(), block, total)
