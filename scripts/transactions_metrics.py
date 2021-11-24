import os
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from brownie.network.contract import Contract

import pandas as pd
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
    

def _user_balances(df: pd.DataFrame, block: int) -> pd.DataFrame:
    def _get_price(vault):
        try: 
            return Decimal(get_price(vault,block))
        except TypeError:
            return Decimal(get_price(Contract(vault).token(),block))
    sum_in = df[df['to'] != ZERO_ADDRESS][['to','vault','value']].rename(columns={'to':'user','value':'in'}).groupby(['user','vault']).sum().reset_index().set_index(['user','vault'])
    sum_out = df[df['from'] != ZERO_ADDRESS][['from','vault','value']].rename(columns={'from':'user','value':'out'}).groupby(['user','vault']).sum().reset_index().set_index(['user','vault'])
    df = sum_in[sum_in['in'] > 0].join(sum_out).fillna(0).reset_index()
    df['balance'] = df['in'] - df['out']
    df['price'] = df['vault'].apply(_get_price)
    df['usd_bal'] = df['balance'] * df['price']
    return df

def _count_users_by_num_vaults_used(df: pd.DataFrame):
    df = df[['to','vault']].groupby(['to','vault']).size().reset_index()
    df = df[df[0] > 0].groupby(['to']).size().reset_index()
    return {f'num wallets used {num} vaults': val for num, val in df.groupby([0]).size().items()}

def _export_block(df,block):
    print(f'exporting block {block}')
    df = df[df['block'] <= block]
    user_balances = _user_balances(df,block)
    data = {'stats': _count_users_by_num_vaults_used(df)}
    data['stats']['total_users'] = len(_users(df))
    data['vaults'] = {
        vault: {
            'lifetime_users': len(_users(df,vault=vault)),
            'user_balances': {
                row.user: {
                    'token_bal': row.balance,
                    'usd_bal': row.usd_bal
                    } for row in user_balances[user_balances['vault'] == vault].itertuples() if row.balance > 0
                },
            'churned_users': sum(1 for row in user_balances[user_balances['vault'] == vault].itertuples() if row.usd_bal <= 10),
            } for vault in tqdm(_vaults(df))
        }
    sum_bals = user_balances[['user','usd_bal']].groupby('user').sum().reset_index()
    data['stats']['$1k+'] = sum(1 for row in sum_bals.itertuples() if row.usd_bal >   1000)
    data['stats']['$10k+'] = sum(1 for row in sum_bals.itertuples() if row.usd_bal >  10000)
    data['stats']['$100k+'] = sum(1 for row in sum_bals.itertuples() if row.usd_bal > 100000)
    data['stats']['$1m+'] = sum(1 for row in sum_bals.itertuples() if row.usd_bal >   1000000)
    data['stats']['$10m+'] = sum(1 for row in sum_bals.itertuples() if row.usd_bal >  10000000)
    data['stats']['$100m+'] = sum(1 for row in sum_bals.itertuples() if row.usd_bal > 100000000)
    print(sum_bals)
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

        # user balances
        users_df = pd.melt(
            vaults_df[['block','vault']].join(vaults_df['user_balances'].apply(pd.Series)),
            id_vars=['block','vault']).dropna().rename(columns={'variable':'address'}
            )
        users_df = users_df.drop(columns=['value']).join(users_df['value'].apply(pd.Series))
        print(users_df)
        users_df.to_csv('./reports/user_stats.csv', index=False)
