import time
from decimal import Decimal

import pandas as pd
from brownie import ZERO_ADDRESS, chain, web3
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.events import decode_logs, get_logs_asap
from yearn.prices import magic
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

CACHE_PATH = './reports/transactions.csv'
CHUNK_SIZE_BLOCKS = 25000

registryV1 = RegistryV1()
registryV2 = RegistryV2()

def _read_cache():
    try:
        return pd.read_csv(CACHE_PATH)
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
    price = _get_price(event, vault)
    return {
        'block': event.block_number,
        'timestamp': chain[event.block_number].timestamp,
        'hash': event.transaction_hash.hex(),
        'log_index': event.log_index,
        'vault': vault,
        'symbol': vault_symbol,
        'type': _event_type(event, vault.address),
        'from': event['from'],
        'to': event['to'],
        'value': Decimal(event['value']) / Decimal(10 ** vault_decimals),
        'price': price,
        'value_usd': Decimal(event['value']) / Decimal(10 ** vault_decimals) * Decimal(price)
    }

def _get_price(event, vault):
    while True:
        try:
            return magic.get_price(vault.address, event.block_number)
        except TypeError:
            if event.block_number == 10532764 and vault.address == '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e':
                # magic.get_price fails because all liquidity was removed for testing and `share_price` returns None
                return 1
        except ConnectionError:
            # Try again
            time.sleep(1)

def _event_type(event, vault_address) -> str:
    if event['from'] == ZERO_ADDRESS:
        return 'deposit'
    elif event['to'] == ZERO_ADDRESS:
        return 'withdrawal'
    elif event['from'] == vault_address:
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
    return pd.DataFrame([_process_event(event, vault, vault_symbol, vault_decimals) for event in tqdm(events)])
    
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
        df.to_csv(CACHE_PATH, index=False)
        print(f'all vault transfers exported to {CACHE_PATH}')

