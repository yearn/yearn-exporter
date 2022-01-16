import logging
from datetime import datetime, timezone

from yearn.historical_helper import export_historical, time_tracking
from yearn.treasury.treasury import YearnTreasury
from yearn.utils import closest_block_after_timestamp

logger = logging.getLogger('yearn.historical_treasury_exporter')

def main():
    start = datetime.now(tz=timezone.utc)
    # end: 2020-07-21 first treasury tx
    end = datetime(2020, 7, 21, 10, 1, tzinfo=timezone.utc)
    export_historical(
        start,
        end,
        export_chunk,
        export_snapshot,
        'treasury_assets'
    )


def export_chunk(chunk, export_snapshot_func):
    treasury = YearnTreasury()
    for snapshot in chunk:
        ts = snapshot.timestamp()
        export_snapshot_func(
            {
                'treasury': treasury,
                'snapshot': snapshot,
                'ts': ts,
                'exporter_name': 'historical_treasury'
            }
        )


@time_tracking
def export_snapshot(treasury, snapshot, ts, exporter_name):
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    treasury.export(block, ts)
    logger.info("exported treasury snapshot %s", snapshot)
