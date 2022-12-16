import json
import logging
from datetime import datetime, timezone
from time import time

import sentry_sdk
from brownie import Contract, chain
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.utils import closest_block_after_timestamp, safe_views
from yearn.snapshot_range_helper import (start_bidirectional_export, time_tracking)
from yearn.outputs.victoria.output_helper import _build_item, _post
from yearn.outputs.victoria import output_duration

sentry_sdk.set_tag('script','veyfi_exporter')

logger = logging.getLogger('yearn.veyfi_exporter')

VEYFI = {
    Network.Mainnet: '0x90c1f9220d90d3966FbeE24045EDd73E1d588aD5',
}


class VotingYFI:
    def __init__(self):
        self.veyfi = Contract.from_abi(
            name='VotingYFI',
            address=VEYFI[chain.id],
            abi=json.load(open('interfaces/veyfi/VotingYFI.json'))
        )
        self._views = safe_views(self.veyfi.abi)

    def describe(self, block=None):
        # TODO: this currently only fetches totalSupply and supply
        #       will need to parse events & transactions
        try:
            results = fetch_multicall(
                *[[self.veyfi, view] for view in self._views], block=block
            )
            info = dict(zip(self._views, results))
        except ValueError as e:
            info = {}
        return info


def main():
    if chain.id == Network.Mainnet:
        start = datetime(2022, 12, 7, 0, tzinfo=timezone.utc)
        data_query = 'veyfi{network="ETH"}'
    else:
        raise NotImplementedError("Only Mainnet is supported")

    start_bidirectional_export(start, export_snapshot, data_query)


@time_tracking
def export_snapshot(snapshot, ts):
    start = time()
    block = closest_block_after_timestamp(ts, wait_for=True)
    assert block is not None, "no block after timestamp found"
    export_veyfi(block, ts)
    duration = time() - start
    output_duration.export(duration, 1, "veyfi", ts)
    logger.info("exported veyfi snapshot %s took %.3fs", snapshot, time() - start)


def export_veyfi(block, timestamp):
    data = VotingYFI().describe(block=block)
    metrics_to_export = []
    for key, value in data.items():
        item = _build_item(
            "veyfi",
            ['param'],
            [key],
            value,
            timestamp,
        )
        metrics_to_export.append(item)
    _post(metrics_to_export)
