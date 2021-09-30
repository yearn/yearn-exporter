import logging
import os
import time
from datetime import datetime, timedelta, timezone

from yearn.yearn import Yearn
from yearn.utils import closest_block_after_timestamp
from itertools import count

import requests

logger = logging.getLogger('yearn.historical_exporter')


def main():
    start = datetime.now(tz=timezone.utc)
    # end: 2020-02-12 first iearn deployment
    end = datetime(2020, 2, 12, tzinfo=timezone.utc)

    yearn = Yearn()

    start_daily = start.replace(hour=0, minute=0, second=0, microsecond=0)
    daily = _generate_snapshot_range(start_daily, end, timedelta(days=1))
    for day in daily:
        _interval_export(yearn, day)

    start_hourly = start.replace(minute=0, second=0, microsecond=0)
    hourly = _generate_snapshot_range(start_hourly, end, timedelta(hours=1))
    for hour in hourly:
        _interval_export(yearn, hour)


def _interval_export(yearn, snapshot):
    ts = snapshot.timestamp()
    if _has_data(ts):
        logger.info("data already present for snapshot %s, ts %d", snapshot, ts)
        return

    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    yearn.export(block, ts)
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
        result = response.json
        return result['status'] == 'success' and len(result['data']['results']) > 0


def _generate_snapshot_range(start, end, interval):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        else:
            yield snapshot
