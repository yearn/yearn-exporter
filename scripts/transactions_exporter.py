import logging
import time
import warnings
from decimal import Decimal
from typing import Optional

import pandas as pd
import sentry_sdk
from brownie import ZERO_ADDRESS, chain, web3
from brownie.exceptions import BrownieEnvironmentWarning
from pony.orm import db_session
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.entities import UserTx
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import BatchSizeError
from yearn.networks import Network
from yearn.outputs.postgres.utils import (cache_address, cache_chain, cache_token,
                                          last_recorded_block)
from yearn.prices import magic
from yearn.typing import Block
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','transactions_exporter')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

yearn = Yearn(load_strategies=False)

logger = logging.getLogger('yearn.transactions_exporter')

BATCH_SIZE = {
    Network.Mainnet: 5_000,
    Network.Fantom: 20_000,
    Network.Gnosis: 2_000_000,
}[chain.id]

FIRST_END_BLOCK = {
    Network.Mainnet: 9_480_000, # NOTE block some arbitrary time after iearn's first deployment
    Network.Fantom: 5_000_000, # NOTE block some arbitrary time after v2's first deployment
    Network.Gnosis: 21_440_000, # # NOTE block some arbitrary time after first vault deployment
}[chain.id]


def main():
    _cached_thru_from_last_run = 0
    while True:
        cached_thru = last_recorded_block(UserTx)
        _check_for_infinite_loop(_cached_thru_from_last_run, cached_thru)
        process_and_cache_user_txs(cached_thru)
        _cached_thru_from_last_run = cached_thru
        time.sleep(1)


@db_session
def process_and_cache_user_txs(last_saved_block=None):
    # NOTE: We look 50 blocks back to avoid uncles and reorgs
    max_block_to_cache = chain.height - 50
    start_block = last_saved_block + 1 if last_saved_block else None
    end_block = (
        FIRST_END_BLOCK if start_block is None
        else start_block + BATCH_SIZE if start_block + BATCH_SIZE < max_block_to_cache
        else max_block_to_cache
    )
    if start_block and start_block > end_block:
        end_block = start_block
    df = pd.DataFrame()
    for vault in yearn.active_vaults_at(end_block):
        df = pd.concat([df, get_token_transfers(vault.vault, start_block, end_block)])
    if len(df):
        # NOTE: We want to insert txs in the order they took place, so wallet exporter
        #       won't have issues in the event that transactions exporter fails mid-run.
        df = df.sort_values('block')  
        for index, row in df.iterrows():
            # this addresses one tx with a crazy price due to yvpbtc v1 pricePerFullShare bug.
            price = row.price if len(str(round(row.price))) <= 20 else 99999999999999999999
            usd = row.value_usd if len(str(round(row.value_usd))) <= 20 else 99999999999999999999
            
            UserTx(
                chain=cache_chain(),
                vault=cache_token(row.token),
                timestamp=row.timestamp,
                block=row.block,
                hash=row.hash,
                log_index=row.log_index,
                type=row.type,
                from_address=cache_address(row['from']),
                to_address=cache_address(row['to']),
                amount = row.amount,
                price = price,
                value_usd = usd,
                gas_used = row.gas_used,
                gas_price = row.gas_price
                )
        if start_block == end_block:
            logger.info(f'{len(df)} user txs exported to postrges [block {start_block}]')
        else:
            logger.info(f'{len(df)} user txs exported to postrges [blocks {start_block}-{end_block}]')


# Helper functions
def get_token_transfers(token, start_block, end_block) -> pd.DataFrame:
    topics = construct_event_topic_set(
        filter_by_name('Transfer', token.abi)[0],
        web3.codec,
    )
    token_entity = cache_token(token.address)
    events = decode_logs(
        get_logs_asap(token.address, topics, from_block=start_block, to_block=end_block)
    )
    return pd.DataFrame([_process_transfer_event(event, token_entity) for event in events])


def _process_transfer_event(event, token_entity) -> dict:
    sender, receiver, amount = event.values()
    cache_address(sender)
    cache_address(receiver)
    price = _get_price_from_event(event, token_entity)
    if (
        # NOTE magic.get_price() returns erroneous price due to erroneous ppfs
        token_entity.address.address == '0x7F83935EcFe4729c4Ea592Ab2bC1A32588409797'
        and event.block_number == 12869164
    ):
        price = 99999
    txhash = event.transaction_hash.hex()
    return {
        'chainid': chain.id,
        'block': event.block_number,
        'timestamp': chain[event.block_number].timestamp,
        'hash': txhash,
        'log_index': event.log_index,
        'token': token_entity.address.address,
        'type': _event_type(sender, receiver, token_entity.address.address),
        'from': sender,
        'to': receiver,
        'amount': Decimal(amount) / Decimal(10 ** token_entity.decimals),
        'price': price,
        'value_usd': Decimal(amount) / Decimal(10 ** token_entity.decimals) * Decimal(price),
        'gas_used': web3.eth.getTransactionReceipt(txhash).gasUsed,
        'gas_price': web3.eth.getTransaction(txhash).gasPrice
    }


def _get_price_from_event(event, token_entity):
    while True:
        try:
            return magic.get_price(token_entity.address.address, event.block_number, return_price_during_vault_downtime=True)
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
                logger.warn(f'vault: {token_entity.address.address}')
                raise


def _event_type(sender, receiver, vault_address) -> str:
    if sender == ZERO_ADDRESS:
        return 'deposit'
    elif receiver == ZERO_ADDRESS:
        return 'withdrawal'
    elif sender == vault_address:
        return 'v2 fees'
    else:
        return 'transfer'


def _check_for_infinite_loop(cached_thru: Optional[Block], cached_thru_from_last_run: Optional[Block]) -> None:
    if not cached_thru == cached_thru_from_last_run:
        return
    if cached_thru and cached_thru > chain.height - BATCH_SIZE:
        return
    raise BatchSizeError(f'Stuck in infinite loop, increase transactions exporter batch size for {Network(chain.id).name}.')
