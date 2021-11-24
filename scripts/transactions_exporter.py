import time
import warnings
from decimal import Decimal
import logging

import pandas as pd
from brownie import ZERO_ADDRESS, Contract, chain, web3
from brownie.exceptions import BrownieEnvironmentWarning
from joblib import Parallel, delayed
import sqlalchemy
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.events import create_filter, decode_logs, get_logs_asap
from yearn.outputs.postgres.postgres import postgres
from yearn.prices import magic
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2
from ypricemagic.interfaces.ERC20 import ERC20ABI
from yearn.treasury.treasury import Treasury

treasury = Treasury()

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

registryV1 = RegistryV1()
registryV2 = RegistryV2()

logger = logging.getLogger(__name__)

def main():
    for block in chain.new_blocks(height_buffer=1):
        process_and_cache_user_txs(postgres.last_recorded_block('user_txs'))

def active_vaults_at(end_block) -> set:
    v1 = {vault.vault for vault in registryV1.active_vaults_at(end_block)}
    v2 = {vault.vault for vault in registryV2.active_vaults_at(end_block)}
    return v1.union(v2)

def process_and_cache_user_txs(last_saved_block=None):
    max_block_to_cache = chain.height - 50 # We look 50 blocks back to avoid uncles and reorgs
    start_block = last_saved_block + 1 if last_saved_block else None
    end_block = 10650000 if start_block is None else start_block + 500 if start_block + 500 < max_block_to_cache else max_block_to_cache
    df = pd.DataFrame()
    for vault in tqdm(active_vaults_at(end_block)):
        df = df.append(get_token_transfers(vault, start_block, end_block))
    df = df.rename(columns={'token':'vault'})
    df.to_sql('user_txs',postgres.sqla_engine, if_exists='append',index=False)
    print(f'user txs batch {start_block}-{end_block} exported to postrges')


# Helper functions
def get_token_transfers(token, start_block, end_block) -> pd.DataFrame:
    topics = construct_event_topic_set(
        filter_by_name('Transfer', token.abi)[0],
        web3.codec,
    )
    postgres.cache_token(token.address)
    decimals = Contract(token.address).decimals()
    events = decode_logs(get_logs_asap(token.address, topics, from_block = start_block, to_block = end_block))
    return pd.DataFrame(Parallel(1,'threading')(delayed(_process_transfer_event)(event, token, decimals) for event in events))


def _process_transfer_event(event, vault, decimals) -> dict:
    sender, receiver, amount = event.values()
    postgres.cache_address(sender)
    postgres.cache_address(receiver)
    price = _get_price(event, vault)
    if vault.address == '0x7F83935EcFe4729c4Ea592Ab2bC1A32588409797' and event.block_number == 12869164:
        # NOTE magic.get_price() returns erroneous price due to erroneous ppfs
        price = 99999
    if price > 100000:
        logger.warn(f'token: {vault.address}')
        logger.warn(f'price: {price}')
        logger.warn(f'block: {event.block_number}')
    txhash = event.transaction_hash.hex()
    return {
        'chainid':chain.id,
        'block': event.block_number,
        'timestamp': chain[event.block_number].timestamp,
        'hash': txhash,
        'log_index': event.log_index,
        'token': vault.address,
        'type': _event_type(sender, receiver, vault.address),
        'from': sender,
        'to': receiver,
        'amount': Decimal(amount) / Decimal(10 ** decimals),
        'price': price,
        'value_usd': Decimal(amount) / Decimal(10 ** decimals) * Decimal(price),
        'gas_used': web3.eth.getTransactionReceipt(txhash).gasUsed,
        'gas_price': web3.eth.getTransaction(txhash).gasPrice #* 1.0 # force pandas to insert this as decimal not bigint
    }

def _get_price(event, vault):
    while True:
        try:
            try:
                return magic.get_price(vault.address, event.block_number)
            except TypeError: # magic.get_price fails because all liquidity was removed for testing and `share_price` returns None
                return magic.get_price(vault.token(), event.block_number)
        except ConnectionError as e:
            # Try again
            print(f'ConnectionError: {str(e)}')
            time.sleep(1)
        except ValueError as e:
            print(f'ValueError: {str(e)}')
            if str(e) in ["Failed to retrieve data from API: {'status': '0', 'message': 'NOTOK', 'result': 'Max rate limit reached'}","Failed to retrieve data from API: {'status': '0', 'message': 'NOTOK', 'result': 'Max rate limit reached, please use API Key for higher rate limit'}"]:
                # Try again
                print('trying again...')
                time.sleep(5)
            else:
                print(f'vault: {vault.address}')
                raise(str(e))


def _event_type(sender, receiver, vault_address) -> str:
    if sender == ZERO_ADDRESS:
        return 'deposit'
    elif receiver == ZERO_ADDRESS:
        return 'withdrawal'
    elif sender == vault_address:
        return 'v2 fees'
    else:
        return 'transfer'