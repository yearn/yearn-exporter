import logging
import math
import multiprocessing
import os
import time
from datetime import datetime, timedelta, timezone
from itertools import count

import psutil
import requests
from brownie import chain
from joblib import Parallel, delayed
from toolz import partition_all
from yearn.outputs import victoria
from yearn.outputs.postgres.postgres import postgres
from yearn.utils import closest_block_after_timestamp
from yearn.yearn import Yearn

logger = logging.getLogger('yearn.wallet_exporter')

available_memory = psutil.virtual_memory().available / 1e9   # in GB
default_pool_size = max(1, math.floor(available_memory / 8)) # allocate 8GB per worker
POOL_SIZE = int(os.environ.get("POOL_SIZE", default_pool_size))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 50))

postgres_cached_thru_block = postgres.last_recorded_block('user_txs')
postgres_cached_thru_ts = chain[postgres_cached_thru_block].timestamp

def main():
    start = datetime.now(tz=timezone.utc)
    # end: 2020-02-12 first iearn deployment
    end = datetime(2020, 2, 12, tzinfo=timezone.utc)

    interval_map = [
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

    resolutions = [item['resolution'] for item in interval_map]
    # default resolution is hourly
    resolution = os.environ.get("RESOLUTION", "1h")
    if resolution not in resolutions:
        resolution = "1h"

    for entry in interval_map:
        intervals = _generate_snapshot_range(entry["start"], end, entry["interval"])

        logger.info("starting new pool with %d workers", POOL_SIZE)
        Parallel(n_jobs=POOL_SIZE, backend="multiprocessing", verbose=100)(
            delayed(_export_chunk)(chunk) for chunk in partition_all(CHUNK_SIZE, intervals)
        )

        # if we reached the final resolution we're done
        if entry['resolution'] == resolution:
            break


def _export_chunk(chunk):
    yearn = Yearn(load_strategies=False, watch_events_forever=False)
    for interval in chunk:
        _interval_export(yearn, interval)


def _interval_export(yearn, snapshot):
    start_time = time.time()
    ts = snapshot.timestamp()
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    yearn.export_wallets(block, ts)
    duration = time.time() - start_time
    victoria.export_duration(duration, POOL_SIZE, "wallets", ts)
    logger.info("exported historical wallet snapshot %s", snapshot)


def _has_data(ts):
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    # query for iearn metric which was always present
    url = f'{base_url}/api/v1/query?query=aggregate{{param="total wallets"}}&time={ts}'
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

def _postgres_ready(ts):
    return postgres_cached_thru_ts >= ts

def _generate_snapshot_range(start, end, interval):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        else:
            ts = snapshot.timestamp()
            if not _postgres_ready(ts):
                logger.info("txs are still being cached for snapshot %s, ts %d", snapshot, ts)
                continue
            elif _has_data(ts):
                #logger.info("data already present for snapshot %s, ts %d", snapshot, ts)
                continue
            else:
                yield snapshot
