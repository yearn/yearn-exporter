import logging
from datetime import datetime, timezone
from itertools import count

from brownie import chain
from yearn.entities import UserTx
from yearn.historical_helper import export_historical, has_data, time_tracking
from yearn.outputs.postgres.utils import last_recorded_block
from yearn.utils import closest_block_after_timestamp
from yearn.yearn import Yearn

logger = logging.getLogger('yearn.wallet_exporter')

def main():
    start = datetime.now(tz=timezone.utc)
    # end: 2020-02-12 first iearn deployment
    end = datetime(2020, 2, 12, tzinfo=timezone.utc)
    export_historical(
        start,
        end,
        export_chunk,
        export_snapshot,
        'aggregate{param="total wallets"}',
        _generate_snapshot_range
    )


def export_chunk(chunk, export_snapshot_func):
    yearn = Yearn(load_strategies=False, watch_events_forever=False)
    for snapshot in chunk:
        ts = snapshot.timestamp()
        export_snapshot_func(
            {
                'yearn': yearn,
                'snapshot': snapshot,
                'ts': ts,
                'exporter_name': 'wallets'
            }
        )


@time_tracking
def export_snapshot(yearn, snapshot, ts, exporter_name):
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    yearn.export_wallets(block, ts)
    logger.info("exported historical wallet snapshot %s", snapshot)


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
