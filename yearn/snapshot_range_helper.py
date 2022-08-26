import functools
import logging
import os
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Callable, Iterable, Iterator, List, NoReturn, Union

import requests

from yearn.outputs.victoria import output_duration

POOL_SIZE = int(os.environ.get("POOL_SIZE", 4))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 50))
REORG_BUFFER = timedelta(seconds=int(os.environ.get("REORG_BUFFER", "300")))

logger = logging.getLogger('yearn.snapshot_range_helper')

# This allows us to bypass multiprocessing by setting `POOL_SIZE` to `1`. Can be helpful for debugging.
if POOL_SIZE == 1:
    executor = ThreadPoolExecutor(1)
else:
    executor = ProcessPoolExecutor(POOL_SIZE)

# We can save time and calls to Victoria Metrics by skipping snapshots that were already checked in less granular resolutions.
checked = set()


def _raise_any_exceptions(futures: Iterable[Future]):
    for fut in futures:
        if fut.done() and fut.exception():
            raise fut.exception()

def _get_resolution(interval_map) -> str:
    resolutions = [item['resolution'] for item in interval_map]
    # default resolution is hourly
    resolution = os.environ.get('RESOLUTION', '1h')
    if resolution not in resolutions:
        resolution = "1h"
    return resolution

def start_bidirectional_export(
    start: datetime,
    export_snapshot_func: Callable[..., None],
    data_query: str,
    generate_snapshot_range_func: Callable[..., Iterator[datetime]] = None
) -> NoReturn:

    if generate_snapshot_range_func is None:
        generate_snapshot_range_func = _generate_snapshot_range
    
    interval_map = _get_interval_map(datetime.now(tz=timezone.utc))
    resolutions = [item['resolution'] for item in interval_map]
    # default resolution is hourly
    resolution = os.environ.get('RESOLUTION', '1h')
    if resolution not in resolutions:
        resolution = "1h"
    
    futs: List[Future] = []
    forward_snapshots = forward_snapshot_generator(interval_map)
    historical_snapshots = historical_snapshot_generator(start, data_query, interval_map, generate_snapshot_range_func)
    for snapshot in bidirectional_snapshot_generator(forward_snapshots, historical_snapshots):
        futs.append(executor.submit(export_snapshot_func, {'snapshot': snapshot, 'ts': snapshot.timestamp()}))
        _raise_any_exceptions(futs)


def forward_snapshot_generator(interval_map):
    resolution = _get_resolution(interval_map)
    for res in interval_map:
        if res['resolution'] == resolution:
            interval = res['interval']
            # as `end` will already be handled by the historical_snapshot_generator, forward can begin processing from snapshot ``end + interval``
            checkpoint = res['end']
            break

    while True:
        now = datetime.now(tz=timezone.utc)
        # If the next interval is ready, check it in and yield it.
        if now > checkpoint + interval + REORG_BUFFER:
            checkpoint += interval
            yield checkpoint

        # Otherwise, yield None and the bidirectional_snapshot_generator will defer to
        #  the historical_snapshot_generator until the next forward snapshot is ready.
        else:
            yield None


def historical_snapshot_generator(start, data_query, interval_map, generate_snapshot_range_func):
    resolution = _get_resolution(interval_map)
    for entry in interval_map:
        generator = generate_snapshot_range_func(
            start,
            entry["end"],
            entry["interval"],
            data_query
        )
        for snapshot in generator:
            yield snapshot
        if entry['resolution'] == resolution:
            break


def bidirectional_snapshot_generator(forward_snapshot_generator: Iterator[datetime], historical_snapshot_generator: Iterator[datetime]) -> Iterator[datetime]:
    historical_finished = False
    while True:
        # We'll leave 1 work item at a time for each process in the pool.
        while POOL_SIZE <= _num_pending_work_items(executor):
            logger.debug("waiting for idle workers")
            time.sleep(1)
        if (next_forward := next(forward_snapshot_generator)):
            yield next_forward
        elif not historical_finished:
            next_historical_snapshot = next(historical_snapshot_generator, None)
            if next_historical_snapshot is None:
                historical_finished = True
                logger.info("finished processing historical snapshots")
            else: yield next_historical_snapshot
        else:
            # Some arbitrary number of seconds to sleep before checking whether the next interval is ready to export.
            logger.debug('waiting for next timestamp')
            time.sleep(5)


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

        output_duration.export(end-start, POOL_SIZE, exporter_name, ts)
        return result
    return wrap


def _get_interval_map(end):
    return [
        {
            'resolution': '1d',
            'end': end.replace(hour=0, minute=0, second=0, microsecond=0),
            'interval': timedelta(days=1),
        },
        {
            'resolution': '1h',
            'end': end.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(hours=1),
        },
        {
            'resolution': '30m',
            'end': end.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=30),
        },
        {
            'resolution': '15m',
            'end': end.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=15),
        },
        {
            'resolution': '5m',
            'end': end.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=5),
        },
        {
            'resolution': '1m',
            'end': end.replace(second=0, microsecond=0),
            'interval': timedelta(minutes=1),
        },
        {
            'resolution': '30s',
            'end': end.replace(second=0, microsecond=0),
            'interval': timedelta(seconds=30),
        },
        {
            'resolution': '15s',
            'end': end.replace(second=0, microsecond=0),
            'interval': timedelta(seconds=15),
        },
    ]


def has_data(ts, data_query):
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    # query for a metric which should be present
    url = f'{base_url}/api/v1/query?query={data_query}&time={int(ts)}'
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
        snapshot = end - i * interval
        if snapshot < start:
            return
        elif snapshot in checked:
            continue
        else:
            # We can save time and calls to Victoria Metrics by skipping snapshots that were already checked in less granular resolutions.
            checked.add(snapshot)
            ts = snapshot.timestamp()
            if has_data(ts, data_query):
                logger.info("data already present for snapshot %s, ts %d", snapshot, ts)
                continue
            else:
                yield snapshot

def _num_pending_work_items(executor: Union[ProcessPoolExecutor, ThreadPoolExecutor]) -> int:
    if isinstance(executor, ProcessPoolExecutor):
        return len(executor._pending_work_items)
    elif isinstance(executor, ThreadPoolExecutor):
        return executor._work_queue.qsize()
    else:
        raise NotImplementedError("executor type not supported, must be an instance of ProcessPoolExecutor or ThreadPoolExecutor")
