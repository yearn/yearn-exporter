import pandas as pd
import os
from .transactions import CACHE_PATH
from brownie import chain, ZERO_ADDRESS
from datetime import datetime, timedelta
import requests
from itertools import count
from yearn.utils import closest_block_after_timestamp
from tqdm import tqdm

CSV_EXPORT = True
CSV_PATH = './reports/stats.csv'

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
        yield snapshot


def _users(df,vault = None):
    if vault:
        df = df[df['vault'] == vault]
    df = df[df['to'] != ZERO_ADDRESS]
    return df['to'].unique()
    

def _total_users(df: pd.DataFrame):
    return len(_users(df))

def _count_users_by_num_vaults_used(df: pd.DataFrame):
    data = {}
    for user in _users(df):
        ct = len(df[df['to'] == user]['vault'].unique())
        try:
            data[f'wallets that used {ct} vaults'] += 1
        except:
            data[f'wallets that used {ct} vaults'] = 1
    return data

def _export_block(df,block):
    df = df[df['block'] <= block]
    data = _count_users_by_num_vaults_used(df)
    data['total_users'] = _total_users(df)
    return data


def main(block = None):
    df = _read_cache()
    if block:
        df = df[df['block'] <= block]
        return _export_block(df,block)
    data = {block:_export_block(df,block) for block in tqdm(_blocks(df))}
    
    if CSV_EXPORT:
        df = pd.DataFrame(data).transpose()
        df.to_csv(CSV_PATH, index=True)
    

