import logging
import os
import time

from brownie import chain
from yearn.treasury.treasury import Treasury
from yearn.outputs import victoria

logger = logging.getLogger('yearn.treasury_exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))


def main():
    treasury = Treasury(watch_events_forever=True)
    for block in chain.new_blocks(height_buffer=12):
        start_time = time.time()
        treasury.export(block.number, block.timestamp)
        duration = time.time() - start_time
        victoria.export_duration(duration, 1, "treasury_forwards", block.timestamp)
        time.sleep(sleep_interval)
