import logging
import time
from datetime import datetime, timedelta, timezone
from itertools import count

from yearn.entities import Block, Snapshot, db_session
from yearn.utils import closest_block_after_timestamp, get_block_timestamp
from yearn.yearn import Yearn

logger = logging.getLogger("yearn.historical_tvl")


def generate_snapshot_range(start, interval):
    for i in count():
        yield start + i * interval


def main():
    yearn = Yearn(load_strategies=False)
    start = datetime(2020, 2, 12, tzinfo=timezone.utc)  # first iearn deployment
    interval = timedelta(hours=1)
    buffer = timedelta(minutes=5)
    synced = False
    for snapshot in generate_snapshot_range(start, interval):
        while snapshot + buffer > datetime.now().astimezone(timezone.utc):
            if not synced:
                synced = True
                logger.info("synced")
            time.sleep(60)

        with db_session:
            if Block.get(snapshot=snapshot):
                logger.debug("block exists for snapshot=%s", snapshot)
                continue

            logger.debug("inserting snapshot=%s", snapshot)
            block = closest_block_after_timestamp(snapshot.timestamp())
            assert block is not None, "no block after timestamp found"
            assets = yearn.total_value_at(block)
            block_ts = datetime.fromtimestamp(get_block_timestamp(block)).astimezone(timezone.utc)

            new_block = Block(block=block, timestamp=block_ts, snapshot=snapshot)

            for product in assets:
                for name in assets[product]:
                    Snapshot(block=new_block, product=product, name=name, assets=assets[product][name])

            total = sum(sum(x.values()) for x in assets.values())
            logger.info(f"inserted snapshot=%s block=%d tvl=%.0f", snapshot, block, total)
