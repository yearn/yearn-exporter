import logging
import time
import warnings
from decimal import Decimal

import pandas as pd
from brownie import ZERO_ADDRESS, Contract, chain, web3
from brownie.exceptions import BrownieEnvironmentWarning
from pony.orm import db_session
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.entities import UserTx  # , TreasuryTx
from yearn.events import decode_logs, get_logs_asap
from yearn.outputs.postgres.utils import (cache_address, cache_token,
                                          last_recorded_block)
from yearn.prices import magic
from yearn.yearn import Yearn

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

yearn = Yearn(load_strategies=False)

logger = logging.getLogger('yearn.transactions_exporter')

BATCH_SIZE = 5000

def main():
    for block in chain.new_blocks(height_buffer=1):
        process_and_cache_user_txs(last_recorded_block(UserTx))


@db_session
def process_and_cache_user_txs(last_saved_block=None):
    # NOTE: We look 50 blocks back to avoid uncles and reorgs
    max_block_to_cache = chain.height - 50
    start_block = last_saved_block + 1 if last_saved_block else None
    end_block = (
        9480000 if start_block is None # NOTE block some arbitrary time after iearn's first deployment
        else start_block + BATCH_SIZE if start_block + BATCH_SIZE < max_block_to_cache
        else max_block_to_cache
    )
    df = pd.DataFrame()
    for vault in yearn.active_vaults_at(end_block):
        df = pd.concat([df, get_token_transfers(vault.vault, start_block, end_block)])
    if len(df):
        # NOTE: We want to insert txs in the order they took place, so wallet exporter
        #       won't have issues in the event that transactions exporter fails mid-run.
        df = df.sort_values('block')  
        for index, row in df.iterrows():
            UserTx(
                vault=cache_token(row.token),
                timestamp=row.timestamp,
                block=row.block,
                hash=row.hash,
                log_index=row.log_index,
                type=row.type,
                from_address=row['from'],
                to_address=row['to'],
                amount = row.amount,
                price = row.price,
                value_usd = row.value_usd,
                gas_used = row.gas_used,
                gas_price = row.gas_price
                )
        if start_block == end_block:
            logger.warn(f'{len(df)} user txs exported to postrges [block {start_block}]')
        else:
            logger.warn(f'{len(df)} user txs exported to postrges [blocks {start_block}-{end_block}]')


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
    price = _get_price(event, token_entity)
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


def _get_price(event, token_entity):
    while True:
        try:
            try:
                return magic.get_price(token_entity.address.address, event.block_number)
            except TypeError:  # magic.get_price fails because all liquidity was removed for testing and `share_price` returns None
                return magic.get_price(Contract(token_entity.address.address).token(), event.block_number)
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
                logger.warn(f'vault: {token_entity.token.address}')
                raise Exception(str(e))


def _event_type(sender, receiver, vault_address) -> str:
    if sender == ZERO_ADDRESS:
        return 'deposit'
    elif receiver == ZERO_ADDRESS:
        return 'withdrawal'
    elif sender == vault_address:
        return 'v2 fees'
    else:
        return 'transfer'
