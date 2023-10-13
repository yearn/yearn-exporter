import json
import logging
from datetime import datetime, timezone
from typing import List

import sentry_sdk
from brownie import chain
from y import Contract, Network
from y.datatypes import Block
from y.time import closest_block_after_timestamp

from yearn.yeth import Registry
from yearn import constants
from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _build_item, _post
from yearn.outputs.victoria.output_helper import _get_string_label

sentry_sdk.set_tag('script','yeth_exporter')

logger = logging.getLogger('yearn.yeth_exporter')

start = {
    # no yETH pool data before 2023-09-08
    Network.Mainnet: datetime(2023, 9, 8, 0, tzinfo=timezone.utc)
}

def main():
    Exporter(
        name = "yeth",
        data_query = 'yeth{network="ETH"}',
        data_fn = YETH().metrics_for_export,
        export_fn = _post,
        start_block = closest_block_after_timestamp(start[chain.id]),
        concurrency=constants.CONCURRENCY,
        resolution='1d',
    ).run()

class YETH:
    def __init__(self):
        if chain.id != Network.Mainnet:
            raise NotImplementedError(f"Only supports Ethereum Mainnet")
        self.registry = Registry()

    async def describe(self, block=None):
        return await self.registry.describe(block)

    
    async def metrics_for_export(self, block: Block, timestamp: int) -> List:
        metrics_to_export = []
        data = await self.describe(block)
        for product, params in data.items():
            for key, value in params.items():
                address = _get_string_label(params, "address")
                item = _build_item(
                    "yeth",
                    ["product", "param", "address"],
                    [product, key, address],
                    value,
                    timestamp,
                )
                metrics_to_export.append(item)
        return metrics_to_export
