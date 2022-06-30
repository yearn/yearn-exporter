import logging
import os
import time

import sentry_sdk
from brownie import chain
from yearn.outputs.victoria import output_duration
from yearn.prices import constants
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','exporter')

sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))

def main():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        start_time = time.time()
        yearn.export(block.number, block.timestamp)
        duration = time.time() - start_time
        output_duration.export(duration, 1, "forwards", block.timestamp)
        time.sleep(sleep_interval)


def tvl():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        data = yearn.total_value_at(block.number)
        products = list(data.keys())
        if yearn.exclude_ib_tvl and block > constants.ib_snapshot_block:
            products.remove('ib')

        total = sum(sum(vaults.values()) for (product, vaults) in data.items() if product in products)
        print(f"block={block.number} tvl={total}")
        logger.info('exported block=%d tvl=%.0f', block.number, total)
        time.sleep(sleep_interval)
