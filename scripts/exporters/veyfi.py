import json
import logging
from datetime import datetime, timezone
from typing import List

import sentry_sdk
from brownie import chain
from y import Contract, Network
from y.datatypes import Block
from y.time import closest_block_after_timestamp

from yearn.helpers.exporter import Exporter
from yearn.multicall2 import fetch_multicall_async
from yearn.outputs.victoria.victoria import _build_item, _post
from yearn.utils import safe_views

sentry_sdk.set_tag('script','veyfi_exporter')

logger = logging.getLogger('yearn.veyfi_exporter')

start = {
    Network.Mainnet: datetime(2022, 12, 7, 0, tzinfo=timezone.utc)
}

def main():
    Exporter(
        name = "veyfi",
        data_query = 'veyfi{network="ETH"}',
        data_fn = VotingYFI().metrics_for_export,
        export_fn = _post,
        start_block = closest_block_after_timestamp(start[chain.id]),
        concurrency=1000,
    ).run()



VEYFI = {
    Network.Mainnet: '0x90c1f9220d90d3966FbeE24045EDd73E1d588aD5',
}

# TODO: Move this into special module rather than its own exporter
class VotingYFI:
    def __init__(self):
        if chain.id not in VEYFI:
            raise NotImplementedError(f"Only supports {VEYFI.keys()}")

        self.veyfi = Contract.from_abi(
            name='VotingYFI',
            address=VEYFI[chain.id],
            abi=json.load(open('interfaces/veyfi/VotingYFI.json'))
        )
        self._views = safe_views(self.veyfi.abi)

    async def describe(self, block=None):
        # TODO: this currently only fetches totalSupply and supply
        #       will need to parse events & transactions
        try:
            results = await fetch_multicall_async(
                *[[self.veyfi, view] for view in self._views], block=block
            )
            info = dict(zip(self._views, results))
        except ValueError as e:
            info = {}
        return info
    
    async def metrics_for_export(self, block: Block, timestamp: int) -> List:
        metrics_to_export = []
        data = await self.describe(block)
        for key, value in data.items():
            item = _build_item(
                "veyfi",
                ['param'],
                [key],
                value,
                timestamp,
            )
            metrics_to_export.append(item)
        return metrics_to_export
