import logging
import os
import time

from brownie import chain
from yearn.yearn import Yearn
from yearn.outputs import victoria

logger = logging.getLogger('yearn.exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))

def main():
    yearn = Yearn(load_transfers=True)
    for block in chain.new_blocks(height_buffer=1):
        start_time = time.time()
        yearn.export(block.number, block.timestamp)
        duration = time.time() - start_time
        victoria.export_duration(duration, 1, "forwards", block.timestamp)
        time.sleep(sleep_interval)


def tvl():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        data = yearn.total_value_at()
        total = sum(sum(vaults.values()) for vaults in data.values())
        print(f"block={block.number} tvl={total}")
        logger.info('exported block=%d tvl=%.0f', block.number, total)
        time.sleep(sleep_interval)
