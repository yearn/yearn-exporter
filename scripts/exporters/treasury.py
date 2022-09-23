import logging
from datetime import datetime, timezone
from time import time

import sentry_sdk
from brownie import chain
from yearn.networks import Network
from yearn.snapshot_range_helper import (start_bidirectional_export,
                                         time_tracking)
from yearn.utils import closest_block_after_timestamp

sentry_sdk.set_tag('script','treasury_exporter')

logger = logging.getLogger('yearn.treasury_exporter')

def main():
    data_query = 'treasury_assets{network="' + Network.label() + '"}'
    start = {
        Network.Mainnet: datetime(2020, 7, 21, 10, 1, tzinfo=timezone.utc), # first treasury tx
        Network.Fantom: datetime(2021, 10, 12, tzinfo=timezone.utc), # Fantom Multisig deployed
        Network.Gnosis: datetime(2022, 1, 8, 2, 20, 50, tzinfo=timezone.utc), # Block 20_000_000, some time near the first tx in the Gnosis treasury EOA. Further testing is needed to confirm as first tx was not fully apparent on block explorer.
        Network.Arbitrum: datetime(2022, 1, 20, 23, 10, tzinfo=timezone.utc), # first treasury tx time block 4837859
        Network.Optimism: datetime(2022, 8, 6, 20, 1, 18, tzinfo=timezone.utc), # create contract blocks 18100336
    }[chain.id]

    start_bidirectional_export(start, export_snapshot, data_query)


@time_tracking
def export_snapshot(snapshot, ts):
    start = time()
    from yearn.treasury.treasury import _treasury
    block = closest_block_after_timestamp(ts, wait_for=True)
    assert block is not None, "no block after timestamp found"
    _treasury().export(block, ts)
    logger.info("exported treasury snapshot %s took %.3fs", snapshot, time() - start)
