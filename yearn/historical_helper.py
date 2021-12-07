import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from itertools import count
import functools

import requests
from joblib import Parallel, delayed
from toolz import partition_all
from yearn.outputs import victoria
from yearn.yearn import Yearn
from datetime import timedelta

POOL_SIZE = int(os.environ.get("POOL_SIZE", 1))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 50))

logger = logging.getLogger('yearn.historical_helper')

def export_historical(start, end, export_chunk_func, export_snapshot_func, data_query, generate_snapshot_range_func=None):
    if generate_snapshot_range_func is None:
        generate_snapshot_range_func = _generate_snapshot_range

    interval_map = _get_interval_map(start)
    resolutions = [item['resolution'] for item in interval_map]
    # default resolution is hourly
    resolution = os.environ.get("RESOLUTION", "1h")
    if resolution not in resolutions:
        resolution = "1h"

    for entry in interval_map:
        snapshots = generate_snapshot_range_func(
            entry["start"],
            end,
            entry["interval"],
            data_query
        )

        chunks = partition_all(CHUNK_SIZE, snapshots)
        batches = partition_all(POOL_SIZE, chunks)
        for b in batches:
            logger.info("starting new pool with %d workers", POOL_SIZE)
            Parallel(n_jobs=POOL_SIZE, backend="multiprocessing", verbose=100)(
                delayed(export_chunk_func)(chunk, export_snapshot_func) for chunk in b
            )

        # if we reached the final resolution we're done
        if entry['resolution'] == resolution:
            break


def time_tracking(export_snapshot_func):
    @functools.wraps(export_snapshot_func)
    def wrap(*args, **kwargs):
        if len(args) == 0:
            raise TypeError("export_snapshot_func needs at least one arg which is a dict!")

        arg_hash = args[0]
        ts = arg_hash.get('ts', datetime.now(tz=timezone.utc).timestamp())
        exporter_name = arg_hash.get('exporter_name', 'mighty_exporter')
        # create args list for all hash keys for easier handling in export_snapshot_func
        le_args = [arg_hash[k] for k in arg_hash.keys()]

        start = time.time()
        result = export_snapshot_func(*le_args, **kwargs)
        end = time.time()

        victoria.export_duration(end-start, POOL_SIZE, exporter_name, ts)
        return result
    return wrap


def _get_interval_map(start):
    return [
        {
            'resolution': '1d',
            'start': start.replace(hour=0, minute=0, second=0, microsecond=0),
            'interval': timedelta(days=1),
        },
        {
            'resolution': '1h',
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(hours=1),
        },
        {
            'resolution': '30m',
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=30),
        },
        {
            'resolution': '15m',
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=15),
        },
        {
            'resolution': '5m',
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=5),
        },
        {
            'resolution': '1m',
            'start': start.replace(second=0, microsecond=0),
            'interval': timedelta(minutes=1),
        },
        {
            'resolution': '30s',
            'start': start.replace(second=0, microsecond=0),
            'interval': timedelta(seconds=30),
        },
        {
            'resolution': '15s',
            'start': start.replace(second=0, microsecond=0),
            'interval': timedelta(seconds=15),
        },
    ]


def _has_data(ts, data_query):
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    # query for a metric which should be present
    url = f'{base_url}/api/v1/query?query={data_query}&time={ts}'
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


def _generate_snapshot_range(start, end, interval, data_query):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        else:
            ts = snapshot.timestamp()
            if _has_data(ts, data_query):
                logger.info("data already present for snapshot %s, ts %d", snapshot, ts)
                continue
            else:
                yield snapshot
