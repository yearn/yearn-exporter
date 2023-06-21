import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Dict, Literal, Set

logger = logging.getLogger(__name__)

Resolution = Literal['1d', '1h', '30m', '15m', '5m', '1m', '30s', '15s']

REORG_BUFFER = timedelta(seconds=int(os.environ.get("REORG_BUFFER", "300"))) # Default: 5 minutes
RESOLUTION: Resolution = os.environ.get('RESOLUTION', '1h') # Default: 1 hour
SLEEP_TIME = int(os.environ.get('SLEEP_TIME', 15)) # Default: 15 seconds


async def _generate_snapshot_range_forward(start: datetime, interval: timedelta):
    for i in count():
        snapshot = start + i * interval
        while snapshot > datetime.now(tz=timezone.utc) + REORG_BUFFER:
            diff = snapshot - datetime.now(tz=timezone.utc) + REORG_BUFFER
            logger.debug(f"SLEEPING {diff}")
            await asyncio.sleep(diff.total_seconds())
        yield snapshot


async def _generate_snapshot_range_historical(end: datetime, resolution, intervals):
    start = intervals[resolution]['start']
    interval = intervals[resolution]['interval']
    last_interval_snapshots = _get_last_interval_snapshots(end, resolution, intervals)
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        if snapshot in last_interval_snapshots:
            continue
        else:
            yield snapshot

def _get_last_interval_snapshots(end: datetime, resolution: Resolution, intervals: Dict[Resolution, Dict]) -> Set[datetime]:
    last_interval = None
    for res in intervals:
        if res == resolution:
            break
        last_interval = intervals[res]
    
    last_interval_snapshots = set()
    
    if last_interval:
        start = last_interval['start']
        interval = last_interval['interval']
        for i in count():
            snapshot = start - i * interval
            if snapshot < end:
                break
            last_interval_snapshots.add(snapshot)
    return last_interval_snapshots

def _get_intervals(start):
    # default resolution is hourly
    resolutions = {
        '1d': {
            'start': start.replace(hour=0, minute=0, second=0, microsecond=0),
            'interval': timedelta(days=1),
        },
        '1h': {
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(hours=1),
        },
        '30m': {
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=30),
        },
        '15m':{
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=15),
        },
        '5m': {
            'start': start.replace(minute=0, second=0, microsecond=0),
            'interval': timedelta(minutes=5),
        },
        '1m': {
            'start': start.replace(second=0, microsecond=0),
            'interval': timedelta(minutes=1),
        },
        '30s': {
            'start': start.replace(second=0, microsecond=0),
            'interval': timedelta(seconds=30),
        },
        '15s': {
            'start': start.replace(second=0, microsecond=0),
            'interval': timedelta(seconds=15),
        },
    }
    assert RESOLUTION in resolutions, f"resolution {RESOLUTION} not supported. Must be one of {resolutions}"
    intervals = {}
    for res, params in resolutions.items():
        intervals[res] = params
        if res == RESOLUTION:
            break
    return intervals
