import pandas as pd
import os
from .transactions import CACHE_PATH
from brownie import chain
from datetime import datetime, timedelta
import requests
from itertools import count
from yearn.utils import closest_block_after_timestamp
from tqdm import tqdm

def _read_cache():
    try:
        return pd.read_csv(CACHE_PATH)
    except FileNotFoundError:
        raise FileNotFoundError('You must export transactions.csv using `brownie run transactions` before running this script.')


def _blocks(df):
    start = datetime.utcfromtimestamp(chain[df['block'].max().item()].timestamp)
    end = datetime.utcfromtimestamp(chain[df['block'].min().item()].timestamp)

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
    # default resolution is daily
    resolution = os.environ.get("RESOLUTION", "1d")
    if resolution not in resolutions:
        resolution = "1d"

    for entry in interval_map:
        if entry["resolution"] == resolution:
            intervals = _generate_snapshot_range(entry["start"], end, entry["interval"])
            return [
                closest_block_after_timestamp(interval.timestamp()) - 1
                for interval in list(intervals)
            ]

def _generate_snapshot_range(start, end, interval):
    for i in count():
        snapshot = start - i * interval
        if snapshot < end:
            return
        ts = snapshot.timestamp()
        if _has_data(ts):
            continue
        else:
            yield snapshot

def _has_data(ts):
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    # query for iearn metric which was always present
    url = f'{base_url}/api/v1/query?query=stats&time={ts}'
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


def _export_block(df,block):
    pass

def main(block = None):
    df = _read_cache()
    if block:
        df = df[df['block'] <= block]
        _export_block(df,block)
        return
    for block in tqdm(_blocks(df)):
        _export_block(block)

   

