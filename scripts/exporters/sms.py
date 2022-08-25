import logging
from datetime import datetime, timezone
from time import time

import sentry_sdk
from brownie import chain
from yearn.networks import Network
from yearn.snapshot_range_helper import start_bidirectional_export, time_tracking
from yearn.utils import closest_block_after_timestamp

sentry_sdk.set_tag('script','sms_exporter')

logger = logging.getLogger('yearn.sms_exporter')


def main():
    data_query = 'sms_assets{network="' + Network.label() + '"}'
    start = {
        Network.Mainnet: datetime(2021, 1, 28, 9, 10, tzinfo=timezone.utc), # first inbound sms tx
        Network.Fantom: datetime(2021, 6, 17, tzinfo=timezone.utc), # Fantom SMS deployed
        Network.Gnosis: datetime(2022, 2, 3, 23, 45, tzinfo=timezone.utc), # Block 20455212, first tx in SMS
        Network.Arbitrum: datetime(2021, 10, 21, 21, 20, tzinfo=timezone.utc), # block 2434174, first trx
        Network.Optimism: datetime(2022, 8, 6, 17, 27, 45, tzinfo=timezone.utc), # block 18084577
    }[chain.id]

    start_bidirectional_export(start, export_snapshot, data_query)


@time_tracking
def export_snapshot(snapshot, ts):
    start = time()
    from yearn.treasury.treasury import _sms
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    _sms().export(block, ts)
    logger.info("exported sms snapshot %s took %.3fs", snapshot, time() - start)


