import os
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count

import pandas as pd
import requests
from brownie import ZERO_ADDRESS, chain
from joblib import Parallel, delayed
from tqdm import tqdm
from yearn.prices.magic import get_price
from yearn.utils import closest_block_after_timestamp

from .transactions import CACHE_PATH

CSV_EXPORT = True

def _read_cache():
    try:
        return pd.read_pickle(CACHE_PATH)
    except FileNotFoundError:
        raise FileNotFoundError('You must export transactions.pickle using `brownie run transactions` before running this script.')


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


def _vaults(df):
    return df['vault'].unique()

def _users(df,vault = None):
    if vault:
        df = df[df['vault'] == vault]
    df = df[df['to'] != ZERO_ADDRESS]
    return df['to'].unique()
    


def _count_users_by_num_vaults_used(df: pd.DataFrame):
    data = {}
    for user in _users(df):
        ct = len(df[df['to'] == user]['vault'].unique())
        try:
            data[f'num wallets used {ct} vaults'] += 1
        except:
            data[f'num wallets used {ct} vaults'] = 1
    return data

def _process_vault(df,vault):
    print(f'vault: {vault}')
    users = _users(df,vault)
    data = {
        'lifetime_users': len(users),
    }
    return data

def _export_block(df,block):
    df = df[df['block'] <= block]
    data = {'stats': _count_users_by_num_vaults_used(df)}
    data['stats']['total_users'] = len(_users(df))
    data['vaults'] = {vault: _process_vault(df,vault) for vault in _vaults(df)}
    return data


def main(block = None):
    df = _read_cache()
    if block:
        df = df[df['block'] <= block]
        return _export_block(df,block)
    
    blocks = _blocks(df)
    data = dict(zip(blocks,Parallel(8,'multiprocessing')(delayed(_export_block)(df,block) for block in tqdm(blocks))))

    if CSV_EXPORT:
        # yearn stats
        yearn_df = pd.DataFrame(data).transpose()['stats'].apply(pd.Series).fillna(0).astype(int)
        yearn_df = yearn_df[sorted(yearn_df.columns)]
        print(yearn_df)
        yearn_df.to_csv('./reports/stats.csv', index=True)

        # vault stats
        vaults_df = pd.DataFrame(data).transpose()['vaults'].apply(pd.Series).unstack().reset_index().dropna().rename(columns={'level_0':'vault','level_1':'block'})
        vaults_df = vaults_df.drop(columns=[0]).join(vaults_df[0].apply(pd.Series))
        print(vaults_df.drop(columns=['user_balances']))
        vaults_df.drop(columns=['user_balances']).to_csv('./reports/vault_stats.csv', index=False)

