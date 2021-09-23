import logging
import os
import time
from datetime import datetime, timedelta, timezone

from brownie import chain
from yearn.outputs import prometheus
from yearn.yearn import Yearn
from yearn.utils import closest_block_after_timestamp

from itertools import count


logger = logging.getLogger('yearn.exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))

def main():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        start = time.time()
        data = yearn.describe(block.number)
        prometheus.export(block.timestamp, data)
        tvl = sum(vault['tvl'] for product in data.values() for vault in product.values())
        logger.info('exported block=%d tvl=%.0f took=%.3fs', block.number, tvl, time.time() - start)
        time.sleep(sleep_interval)


def tvl():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        data = yearn.total_value_at()
        total = sum(sum(vaults.values()) for vaults in data.values())
        print(f"block={block.number} tvl={total}")
        logger.info('exported block=%d tvl=%.0f', block.number, total)
        time.sleep(sleep_interval)


# start: 2020-02-12 first iearn deployment
def historical(start=datetime(2020, 2, 12, tzinfo=timezone.utc), end=datetime.now(tz=timezone.utc)):
    yearn = Yearn(load_strategies=False)
    interval = timedelta(hours=1)

    for snapshot in _generate_snapshot_range(start, interval):
        if snapshot > end:
            logger.info("done restoring historical data")
            break
        start = time.time()
        block = closest_block_after_timestamp(snapshot.timestamp())
        assert block is not None, "no block after timestamp found"
        data = yearn.describe(block)
        prometheus.export(snapshot.timestamp(), data)
        tvl = sum(vault['tvl'] for product in data.values() for vault in product.values())

        logger.info("inserted snapshot=%s tvl=%.0f took=%.3fs", snapshot, tvl, time.time() - start)


def _generate_snapshot_range(start, interval):
    for i in count():
        yield start + i * interval