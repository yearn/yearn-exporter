import logging
import os
import time
import warnings
from pprint import pprint
from typing import Dict, List, Optional

import pandas as pd
import requests
import sentry_sdk
from brownie import chain, web3
from brownie._config import CONFIG
from brownie.exceptions import BrownieEnvironmentWarning
from brownie.network.contract import _explorer_tokens
from joblib import Parallel, delayed
from pony.orm import TransactionIntegrityError, db_session
from tqdm import tqdm
from web3 import HTTPProvider, Web3
from yearn.entities import TreasuryTx
from yearn.events import decode_logs
from yearn.exceptions import BatchSizeError, PriceError
from yearn.networks import Network
from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                          cache_token, last_recorded_block)
from yearn.prices import constants, magic
from yearn.treasury import accountant
from yearn.treasury.treasury import YearnTreasury
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import contract

sentry_sdk.set_tag('script','treasury_transactions_exporter')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logger = logging.getLogger('yearn.treasury_transactions_exporter')

BATCH_SIZE = {
    Network.Mainnet: 25_000,
    Network.Fantom: 2_000_000,
    Network.Gnosis: 2_000_000,
}[chain.id]

treasury = YearnTreasury(watch_events_forever=True)

def main():
    _cached_thru_from_last_run = 0
    while True:
        cached_thru = last_recorded_block(TreasuryTx)
        _check_for_infinite_loop(_cached_thru_from_last_run, cached_thru)
        process_and_cache_treasury_txs(cached_thru)
        sort()
        _cached_thru_from_last_run = cached_thru
        time.sleep(1)


def process_and_cache_treasury_txs(last_saved_block=None):
    # NOTE: We look 50 blocks back to avoid uncles and reorgs
    max_block_to_cache = chain.height - 50
    start_block = last_saved_block if last_saved_block else treasury._start_block
    end_block = (
        start_block + BATCH_SIZE if start_block + BATCH_SIZE < max_block_to_cache
        else max_block_to_cache
    )
    if start_block and start_block > end_block:
        end_block = start_block

    all_transfers = get_all_transfers(start_block, end_block)
    if all_transfers:
        # NOTE: We want to insert txs in the order they took place, so wallet exporter
        #       won't have issues in the event that transactions exporter fails mid-run.
        df = pd.DataFrame(all_transfers).sort_values('block').drop_duplicates().reset_index()
        inserted = 0
        for index, row in df.iterrows():
            log_index = None if str(row.log_index) in ["None", "nan"] else int(row.log_index)
            try:
                insert_treasury_tx(row, log_index)
                inserted += 1
            except TransactionIntegrityError:
                _validate_integrity_error(row, log_index)
        
        if inserted and start_block == end_block:
            logger.info(f'{inserted} treasury txs exported to postrges [block {start_block}]')
        elif inserted:
            logger.info(f'{inserted} treasury txs exported to postrges [blocks {start_block}-{end_block}]')


@db_session
def insert_treasury_tx(row, log_index) -> bool:
    TreasuryTx(
        chain=cache_chain(),
        block = row.block,
        timestamp = row.timestamp,
        hash = row.hash,
        log_index = log_index,
        from_address = cache_address(row['from']),
        to_address = cache_address(row.to) if row.to else None,
        token = cache_token(row.token),
        amount = row.amount,
        price = row.price,
        value_usd = row.value_usd,
        gas_used = row.gas_used if hasattr(row, 'gas_used') else None,
        gas_price = row.gas_price if hasattr(row, 'gas_price') else None,
        txgroup = accountant.pending_txgroup(),
    )
    

def get_all_transfers(start: Block, end: Block) -> List[Dict]:
    return get_transactions(start, end)  + get_internal_transactions(start, end) + get_token_transfers(start, end)


def get_transactions(start: Block, end: Block) -> List[Dict]:
    logger.debug("Getting eth transactions")
    blockdata = Parallel(96, 'multiprocessing')(delayed(get_transactions_for_block)(treasury.addresses, block) for block in tqdm(range(start,end)))
    return [tx for block in blockdata for tx in block]


def get_transactions_for_block(treasury_addresses: List[Address], block: Block) -> List[Dict]:
    # NOTE Need to do this the hard way to get parallelism
    block = Web3(HTTPProvider(web3.provider.endpoint_uri)).eth.get_block(block, full_transactions=True)

    return [
        {
            'chainid': chain.id,
            'block': tx['blockNumber'],
            'timestamp': block['timestamp'],
            'hash': tx['hash'].hex(),
            'log_index': None,
            'token': "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            'from': tx['from'],
            'to': tx['to'],
            'amount': tx['value'] / 1e18,
            'price': magic.get_price(constants.weth, block['number']),
            'value_usd': tx['value'] / 1e18 * magic.get_price(constants.weth, block['number']),
            'gas_used': web3.eth.getTransactionReceipt(tx['hash']).gasUsed,
            'gas_price': tx['gasPrice']
        }
        for tx in block['transactions']
        if tx['from'] in treasury_addresses or tx['to'] in treasury_addresses
    ]


def get_internal_transactions(start: Block, end: Block) -> List[Dict]:
    logger.debug("Getting internal transactions")
    return [
        tx for address in treasury.addresses
        for tx in get_internal_transactions_for_address(address, start, end)
    ]


def get_internal_transactions_for_address(address: Address, start: Block, end: Block) -> List[Dict]:
    explorer_endpoint = CONFIG.active_network.get("explorer")
    env_token = next((v for k, v in _explorer_tokens.items() if k in explorer_endpoint), None)
    explorer_token = os.environ[env_token]
    internal_txs = []
    while True:
        url = f"{explorer_endpoint}?module=account&action=txlistinternal&address={address}&startblock={start}&sort=asc&apikey={explorer_token}"
        response = requests.get(url).json()['result']
        if response == 'Max rate limit reached':
            logger.warn('trying again...')
            time.sleep(1)
        elif len(response) == 0:
            return internal_txs
        else:
            for tx in response:
                if start <= int(tx['blockNumber']) <= end:
                    amount = int(tx['value']) / 1e18
                    price = magic.get_price(constants.weth, int(tx['blockNumber']))
                    internal_txs.append({
                        'chainid': chain.id,
                        'block': int(tx['blockNumber']),
                        'timestamp': tx['timeStamp'],
                        'hash': tx['hash'],
                        'log_index': None,
                        'token': "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                        'from': tx['from'],
                        'to': tx['to'],
                        'amount': amount,
                        'price': price,
                        'value_usd': amount * price,
                    })

            if _last_full_block_in_response(response) >= end:
                return internal_txs
            
            start = _last_full_block_in_response(response) + 1

def _last_full_block_in_response(response):
    max_block_in_response = max(int(tx['blockNumber']) for tx in response)
    try:
        last_full_block_in_response = max(int(tx['blockNumber']) for tx in response if int(tx['blockNumber']) != max_block_in_response)
    except ValueError as e:
        if str(e) != "max() arg is an empty sequence":
            raise
        last_full_block_in_response = max_block_in_response
    return last_full_block_in_response


def get_token_transfers(start: Block, end: Block) -> List[Dict]:
    logger.debug("Getting token transfers")
    _transfers = [
        transfer['Transfer'][0]
        for transfer in treasury.transfers
        if 'Transfer' in transfer
        and start <= transfer['Transfer'][0].block_number <= end
    ]

    # Try to cache contract definitions for token transfers we couldn't decode.
    busted_token_transfers = [
        transfer['(unknown)'][0]
        for transfer in treasury.transfers
        if 'Transfer' not in transfer
        and start <= transfer['(unknown)'][0].block_number <= end
    ]
    busted_tokens = {transfer.address for transfer in busted_token_transfers if transfer.address}
    for token in busted_tokens:
        contract(token)
    
    # Retry decoding
    failures = []
    for transfer in busted_token_transfers:
        decoded = decode_logs([transfer])
        if "(unknown)" in decoded:
            # Oh well
            failures.append(decoded)
        elif "Transfer" in decoded:
            assert len(decoded["Transfer"]) == 1
            # Woohoo, we fixed it!
            _transfers.append(decoded['Transfer'][0])

    transfers = Parallel(8,'threading')(delayed(_prep_token_transfer_for_insert)(transfer) for transfer in tqdm(_transfers))
    return [x for x in transfers if x]

def _prep_token_transfer_for_insert(transfer):
    address = transfer.address
    source, dest, amount = transfer.values()

    try:
        amount /= 10 ** contract(address).decimals()
    except AttributeError as e:
        # NFTs do this sometimes
        if str(e) == "Contract 'NonfungiblePositionManager' object has no attribute 'decimals'":
            return None

    block = transfer.block_number
    price = get_price(address, block)
    return {
        'chainid': chain.id,
        'block': block,
        'timestamp': web3.eth.get_block(block)['timestamp'],
        'hash': transfer.transaction_hash.hex(),
        'log_index': int(transfer.log_index),
        'token': address,
        'from': source,
        'to': dest,
        'amount': amount,
        'price': price,
        'value_usd': None if price is None else amount * price,
    }


def get_price(address: AddressOrContract, block: Optional[Block]) -> Optional[float]:
    while True:
        try:
            return magic.get_price(address, block)
        except ConnectionError as e:
            # Try again
            logger.warn(f'ConnectionError: {str(e)}')
            time.sleep(1)
        except ValueError as e:
            logger.warn(f'ValueError: {str(e)}')
            if 'Max rate limit reached' in str(e):
                # Try again
                logger.warn('trying again...')
                time.sleep(5)
            else:
                logger.warn(f'vault: {address}')
                logger.warn(e)
                return None
        except PriceError:
            return None


def _check_for_infinite_loop(cached_thru: Optional[Block], cached_thru_from_last_run: Optional[Block]) -> None:
    if not cached_thru == cached_thru_from_last_run:
        return
    if cached_thru and cached_thru > chain.height - BATCH_SIZE:
        return
    raise BatchSizeError(f'Stuck in infinite loop, increase transactions exporter batch size for {Network(chain.id).name}.')


@db_session
def _validate_integrity_error(row, log_index: int) -> TreasuryTx:
    ''' Raises AssertionError if existing object that causes a TransactionIntegrityError is not an EXACT MATCH to the attempted insert. '''
    existing_object = TreasuryTx.get(hash=row.hash, log_index=log_index, chain=cache_chain())
    assert row['to'] == existing_object.to_address.address, (row['to'],existing_object.to_address.address)
    assert row['from'] == existing_object.from_address.address, (row['from'], existing_object.from_address.address)
    assert row['token'] == existing_object.token.address.address, (row['token'], existing_object.token.address.address)
    assert row['amount'] == float(existing_object.amount), (row['amount'], existing_object.amount)
    assert round(row['price'],18) == float(existing_object.price) or str(row['price']) == 'nan' and str(existing_object.price).lower() == 'nan', (row['price'], existing_object.price)
    assert round(row['value_usd'],18) == float(existing_object.value_usd) or str(row['value_usd']) == 'nan' and str(existing_object.value_usd).lower() == 'nan', (row['value_usd'], existing_object.value_usd)
    assert row['block'] == existing_object.block, (row['value_usd'], existing_object.value_usd)
    assert row['timestamp'] == existing_object.timestamp, (row['timestamp'], existing_object.timestamp)
    # NOTE All good!

@db_session
def sort():
    accountant.sort_txs(accountant.unsorted_txs())