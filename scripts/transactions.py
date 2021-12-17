import time
from decimal import Decimal

import pandas as pd
from brownie import ZERO_ADDRESS, chain, web3
from joblib import Parallel, delayed
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.events import decode_logs, get_logs_asap
from yearn.prices import magic
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

CACHE_PATH = './cache/transactions.pickle'
CHUNK_SIZE_BLOCKS = 25000

registryV1 = RegistryV1()
registryV2 = RegistryV2()

def _read_cache():
    try:
        return pd.read_pickle(CACHE_PATH)
    except FileNotFoundError:
        return None

def _blocks(cache):
    start_block = None if cache is None else cache['block'].max().item() + 1
    end_block = chain.height - 50 if start_block else 10550000 # NOTE: we look 50 blocks back to avoid uncles and reorgs
    if start_block and end_block - start_block > CHUNK_SIZE_BLOCKS:
        end_block = start_block + CHUNK_SIZE_BLOCKS
    print(f"start block: {start_block}")
    print(f"end block: {end_block}")
    return start_block,end_block

def active_vaults_at(end_block) -> set:
    v1 = {vault.vault for vault in registryV1.active_vaults_at(end_block)}
    v2 = {vault.vault for vault in registryV2.active_vaults_at(end_block)}
    return v1.union(v2)

def _process_event(event, vault, vault_symbol, vault_decimals) -> dict:
    sender, receiver, price = _from(event), _to(event), _get_price(event, vault)
    return {
        'block': event.block_number,
        'timestamp': chain[event.block_number].timestamp,
        'hash': event.transaction_hash.hex(),
        'log_index': event.log_index,
        'vault': vault.address,
        'symbol': vault_symbol,
        'type': _event_type(sender, receiver, vault.address),
        'from': sender,
        'to': receiver,
        'value': Decimal(event['value']) / Decimal(10 ** vault_decimals),
        'price': price,
        'value_usd': Decimal(event['value']) / Decimal(10 ** vault_decimals) * Decimal(price)
    }

def _get_price(event, vault):
    while True:
        try:
            return magic.get_price(vault.address, event.block_number)
        except TypeError: # magic.get_price fails because all liquidity was removed for testing and `share_price` returns None
            try:
                return magic.get_price(vault.token(), event.block_number)
            except:
                print(f'vault: {vault.address}')
                raise
        except ConnectionError as e:
            # Try again
            print(f'ConnectionError: {str(e)}')
            time.sleep(1)
        except ValueError as e:
            print(f'ValueError: {str(e)}')
            if str(e) == "Failed to retrieve data from API: {'status': '0', 'message': 'NOTOK', 'result': 'Max rate limit reached'}":
                # Try again
                print(str(e))
                print('trying again...')
                time.sleep(5)
            else:
                print(f'vault: {vault.address}')
                raise

def _from(event):
    try:
        return event['from']
    except:
        return event['sender']

def _to(event):
    try:
        return event['from']
    except:
        return event['sender']

def _event_type(sender, receiver, vault_address) -> str:
    if sender == ZERO_ADDRESS:
        return 'deposit'
    elif receiver == ZERO_ADDRESS:
        return 'withdrawal'
    elif sender == vault_address:
        return 'v2 fees? must confirm'
    else:
        return 'transfer'

def _vault_transfers(vault, start_block, end_block) -> pd.DataFrame:
    vault_symbol, vault_decimals = vault.symbol(), vault.decimals()
    topics = construct_event_topic_set(
        filter_by_name('Transfer', vault.abi)[0],
        web3.codec,
    )
    events = decode_logs(get_logs_asap(vault.address, topics, from_block = start_block, to_block = end_block))
    return pd.DataFrame([Parallel(8,'threading')(delayed(_process_event)(event, vault, vault_symbol, vault_decimals) for event in tqdm(events))])
    
def main():
    while True:
        cache = _read_cache()
        start_block, end_block = _blocks(cache)
        df = pd.DataFrame()
        for vault in tqdm(active_vaults_at(end_block)):
            df = df.append(_vault_transfers(vault, start_block, end_block))
        if cache is not None:
            df = cache.append(df)
        df = df.sort_values(by='block')
        df.to_pickle(CACHE_PATH)
        print(f'all vault transfers exported to {CACHE_PATH}')

