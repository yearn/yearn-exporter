import logging
import os
from datetime import datetime, timedelta, timezone
import time
import math

from yearn.yearn import Yearn
from yearn.outputs import victoria
from yearn.utils import closest_block_after_timestamp
from itertools import count
from toolz import partition_all
from joblib import Parallel, delayed
import multiprocessing
import requests
import psutil

logger = logging.getLogger('yearn.historical_exporter')

available_memory = psutil.virtual_memory().available / 1e9   # in GB
default_pool_size = max(1, math.floor(available_memory / 8)) # allocate 8GB per worker
POOL_SIZE = int(os.environ.get("POOL_SIZE", default_pool_size))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 50))

def main():
    start = datetime.now(tz=timezone.utc)
    # end: 2020-02-12 first iearn deployment
    end = datetime(2020, 2, 12, tzinfo=timezone.utc)

    interval_map = [
        {
          'start': start.replace(hour=0, minute=0, second=0, microsecond=0),
          'interval': timedelta(days=1),
        },
        {
          'start': start.replace(minute=0, second=0, microsecond=0),
          'interval': timedelta(hours=1),
        },
    ]

    for entry in interval_map:
        intervals = _generate_snapshot_range(entry["start"], end, entry["interval"])

        logger.info("starting new pool with %d workers", POOL_SIZE)
        Parallel(n_jobs=POOL_SIZE, backend="multiprocessing", verbose=100)(
            delayed(_export_chunk)(chunk) for chunk in partition_all(CHUNK_SIZE, intervals)
        )


def _export_chunk(chunk):
    yearn = Yearn(watch_events=False)
    for interval in chunk:
        _interval_export(yearn, interval)


def _interval_export(yearn, snapshot):
    start_time = time.time()
    ts = snapshot.timestamp()
    if _has_data(ts):
        logger.info("data already present for snapshot %s, ts %d", snapshot, ts)
        return

    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    yearn.export(block, ts)
    duration = time.time() - start_time
    victoria.export_duration(duration, POOL_SIZE, "historical", ts)
    logger.info("exported historical snapshot %s", snapshot)


def _has_data(ts):
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    # query for iearn metric which was always present
    url = f'{base_url}/api/v1/query?query=iearn&time={ts}'
    headers = {
        'Connection': 'close',
    }
    with requests.Session() as session:
        response = session.get(
            url = url,
            headers = headers
        )
        result = response.json()
        return result['status'] == 'success' and len(result['data']['result']) > 0


def _generate_snapshot_range(start, end, interval):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        else:
            yield snapshot
