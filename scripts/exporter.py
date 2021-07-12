import logging
import os
import time
from tokenize import endpats
from tabulate import tabulate

from brownie import chain
from yearn.outputs import prometheus
from yearn.yearn import Yearn

logger = logging.getLogger('yearn.exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))


def main():
    prometheus.start(8800)
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        start = time.time()
        data = yearn.describe(block.number)
        prometheus.export(data)
        for product in data.values():
            if hasattr(product, 'values'):
                for vault in product.values():
                    if vault['tvl'] and isinstance(vault['tvl'], float) == False:
                        tvl = sum(vault['tvl'])
                        logger.info('exported block=%d tvl=%.0f took=%.3fs', block.number, tvl, time.time() - start)
            else:
                for pool in product:
                    logger.info(
                        'exported block=%d composition=%.0f name=%s took=%.3fs',
                        block.number,
                        pool["ratio"],
                        pool["pool_name"],
                        time.time() - start,
                    )
            time.sleep(sleep_interval)


def tvl():
    yearn = Yearn()
    for block in chain.new_blocks(height_buffer=1):
        data = yearn.total_value_at()
        total = sum(sum(vaults.values()) for vaults in data.values())
        print(f"block={block.number} tvl={total}")
        logger.info('exported block=%d tvl=%.0f', block.number, total)
        time.sleep(sleep_interval)
