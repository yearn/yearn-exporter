import logging
import os
import time
from datetime import datetime, timedelta

from brownie import chain
from yearn.outputs import victoria
from yearn.yearn import Yearn
from yearn.utils import closest_block_after_timestamp
from itertools import count
from yearn.config import Config

logger = logging.getLogger('yearn.exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))

def main():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        export(yearn, block.number, block.timestamp)
        time.sleep(sleep_interval)


def export(yearn, block_number, block_ts):
    start = time.time()
    data = yearn.describe(block_number)
    victoria.export(block_ts, data)
    tvl = sum(vault['tvl'] for product in data.values() for vault in product.values())
    logger.info('exported block=%d tvl=%.0f took=%.3fs', block_number, tvl, time.time() - start)


def tvl():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        data = yearn.total_value_at()
        total = sum(sum(vaults.values()) for vaults in data.values())
        print(f"block={block.number} tvl={total}")
        logger.info('exported block=%d tvl=%.0f', block.number, total)
        time.sleep(sleep_interval)


# end: 2020-02-12 first iearn deployment
def historical_export(start=datetime.now(), end=datetime(2020, 2, 12)):
    yearn = Yearn()
    Config().with_events = False

    start_daily = start.replace(hour=0, minute=0, second=0, microsecond=0)
    daily = _generate_snapshot_range(start_daily, end, timedelta(days=1))
    for day in daily:
        _interval_export(yearn, day)

    start_hourly = start.replace(minute=0, second=0, microsecond=0)
    hourly = _generate_snapshot_range(start_hourly, end, timedelta(hours=1))
    for hour in hourly:
        _interval_export(yearn, hour, skip_midnight=True)


def _interval_export(yearn, snapshot, skip_midnight=False):
    if skip_midnight and snapshot.hour == 0 and snapshot.minute == 0:
        return

    ts = snapshot.timestamp()
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    export(yearn, block, ts)
    logger.info("exported historical snapshot %s", snapshot)


def _generate_snapshot_range(start, end, interval):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        else:
            yield snapshot
