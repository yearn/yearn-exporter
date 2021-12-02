import logging
import time
from datetime import datetime, timezone
from yearn.historical_helper import export_historical, time_tracking
from yearn.utils import closest_block_after_timestamp
from yearn.yearn import Yearn

logger = logging.getLogger('yearn.historical_exporter')

def main():
    start = datetime.now(tz=timezone.utc)
    # end: 2020-02-12 first iearn deployment
    end = datetime(2020, 2, 12, 0, 1, tzinfo=timezone.utc)
    export_historical(
        start,
        end,
        export_chunk,
        export_snapshot,
        'iearn'
    )


def export_chunk(chunk, export_snapshot_func):
    yearn = Yearn(watch_events_forever=False)
    for snapshot in chunk:
        ts = snapshot.timestamp()
        export_snapshot_func(
            {
                'yearn': yearn,
                'snapshot': snapshot,
                'ts': ts,
                'exporter_name': 'historical'
            }
        )

@time_tracking
def export_snapshot(yearn, snapshot, ts, exporter_name):
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    yearn.export(block, ts)
    logger.info("exported historical snapshot %s", snapshot)
