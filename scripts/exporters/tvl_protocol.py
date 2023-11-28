import logging
import random
from typing import List

import sentry_sdk
from brownie import chain

from yearn import constants
from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _build_item, _post

sentry_sdk.set_tag('script','tvl_protocol_exporter')
logger = logging.getLogger('yearn.tvl_protocol_exporter')

def main():
    Exporter(
        name = "tvl_protocol",
        data_query = 'tvl_protocol{network="ETH"}',
        data_fn = TvlProtocol().metrics_for_export,
        export_fn = _post,
        start_block = chain.height,
        concurrency=constants.CONCURRENCY
    # as this is ingested via API, we don't query historical data
    ).run(direction = "forward")


class TvlProtocol:
    def __init__(self):
        if chain.id != 1:
            raise NotImplementedError(f"Only supports Ethereum Mainnet")

    async def describe(self, block=None):
        # TODO replace with custom code that gets a CSV from API or similar and formats it into this interface:
        return [
            { "protocol": "aaa", "value": random.randint(1e3, 1e9) },
            { "protocol": "bbb", "value": random.randint(1e3, 1e9) },
            { "protocol": "ccc", "value": random.randint(1e3, 1e9) },
        ]

    async def metrics_for_export(self, block, timestamp) -> List:
        metrics_to_export = []
        data = await self.describe(block)
        for obj in data:
            # TODO each item has a protocol label and the value (tvl) attached, the network is automagically added as a separate label
            item = _build_item(
                "tvl_protocol",
                ["protocol"],
                [obj["protocol"]],
                obj["value"],
                timestamp,
            )
            metrics_to_export.append(item)
        return metrics_to_export
