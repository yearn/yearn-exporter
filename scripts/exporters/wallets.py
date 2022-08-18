import logging
from datetime import datetime, timezone
from itertools import count
from time import time

import sentry_sdk
from brownie import chain
from yearn.entities import UserTx
from yearn.outputs.postgres.utils import last_recorded_block
from yearn.snapshot_range_helper import (has_data, start_bidirectional_export,
                                         time_tracking)
from yearn.utils import closest_block_after_timestamp

sentry_sdk.set_tag('script','wallet_exporter')

logger = logging.getLogger('yearn.wallet_exporter')

def main():
    while True:
        # start: 2020-02-12 first iearn deployment
        start = datetime(2020, 2, 12, tzinfo=timezone.utc)
        start_bidirectional_export(
            start,
            export_snapshot,
            'aggregate{param="total wallets"}',
            _generate_snapshot_range
        )


@time_tracking
def export_snapshot(snapshot, ts):
    start = time()
    from yearn.yearn import _yearn_lite
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    _yearn_lite().export_wallets(block, ts)
    logger.info("exported wallets snapshot %s took %.3fs", snapshot, time() - start)


def _postgres_ready(ts):
    postgres_cached_thru_block = last_recorded_block(UserTx)
    postgres_cached_thru_ts = 0
    if postgres_cached_thru_block:
        postgres_cached_thru_ts = chain[postgres_cached_thru_block].timestamp

    return postgres_cached_thru_ts >= ts


def _generate_snapshot_range(start, end, interval, data_query):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        else:
            ts = snapshot.timestamp()
            if not _postgres_ready(ts):
                logger.info(
                    "txs are still being cached for snapshot %s, ts %d", snapshot, ts
                )
                continue
            elif has_data(ts, data_query):
                # logger.info("data already present for snapshot %s, ts %d", snapshot, ts)
                continue
            else:
                yield snapshot
