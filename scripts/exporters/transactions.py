import asyncio
import logging
import time
import warnings
from decimal import Decimal
from typing import Optional

import dank_mids
import pandas as pd
import sentry_sdk
from async_lru import alru_cache
from brownie import ZERO_ADDRESS, chain, web3
from brownie.exceptions import BrownieEnvironmentWarning
from brownie.network.event import _EventItem
from evmspec.data import uint
from msgspec import Struct, json
from multicall.utils import await_awaitable
from pony.orm import db_session
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y import ERC20, Network, get_block_timestamp_async
from y.utils.events import get_logs_asap

from yearn.entities import UserTx
from yearn.events import decode_logs
from yearn.exceptions import BatchSizeError
from yearn.outputs.postgres.utils import address_dbid, chain_dbid, last_recorded_block, token_dbid
from yearn.prices.magic import _get_price
from yearn.typing import Block
from yearn.utils import threads
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','transactions_exporter')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

yearn = Yearn()

logger = logging.getLogger('yearn.transactions_exporter')

BATCH_SIZE = {
    Network.Mainnet: 5_000,
    Network.Fantom: 100_000,
    Network.Gnosis: 2_000_000,
    Network.Arbitrum: 50_000_000,
    Network.Optimism: 4_000_000,
    Network.Base: 2_000_000,
}[chain.id]

FIRST_END_BLOCK = {
    Network.Mainnet: 9_480_000, # NOTE block some arbitrary time after iearn's first deployment
    Network.Fantom: 5_000_000, # NOTE block some arbitrary time after v2's first deployment
    Network.Gnosis: 21_440_000, # # NOTE block some arbitrary time after first vault deployment
    Network.Arbitrum: 4_837_859,
    Network.Optimism: 18_111_485,
    Network.Base: 3_571_971,
}[chain.id]

STARTED_BLOCK = chain.height

def main():
    _cached_thru_from_last_run = 0
    while True:
        start = time.time()
        cached_thru = last_recorded_block(UserTx)
        _check_for_infinite_loop(_cached_thru_from_last_run, cached_thru)
        await_awaitable(process_and_cache_user_txs(cached_thru))
        _cached_thru_from_last_run = cached_thru

        if cached_thru >= STARTED_BLOCK:
            # minimum 5m loop interval reduces node usage massively
            if sleep_time := max(0, (start + 5 * 60) - time.time()):
                time.sleep(sleep_time)

async def process_and_cache_user_txs(last_saved_block=None):
    # NOTE: We look 50 blocks back to avoid uncles and reorgs
    max_block_to_cache = chain.height - 50
    start_block = last_saved_block + 1 if last_saved_block else None
    end_block = (
        FIRST_END_BLOCK
        if start_block is None
        else min(start_block + BATCH_SIZE, max_block_to_cache)
    )
    if start_block and start_block > end_block:
        end_block = start_block
    vaults = await yearn.active_vaults_at(end_block)
    df = pd.concat(await asyncio.gather(*[get_token_transfers(vault.vault, start_block, end_block) for vault in vaults])) if vaults else pd.DataFrame()
    if len(df):
        # NOTE: We want to insert txs in the order they took place, so wallet exporter
        #       won't have issues in the event that transactions exporter fails mid-run.
        df = df.sort_values('block')  
        await asyncio.gather(*(insert_user_tx(row) for index, row in df.iterrows()))
        if start_block == end_block:
            logger.info(f'{len(df)} user txs exported to postrges [block {start_block}]')
        else:
            logger.info(f'{len(df)} user txs exported to postrges [blocks {start_block}-{end_block}]')

async def insert_user_tx(row) -> None:
    chain_pk = chain_dbid()
    vault_dbid, from_address_dbid, to_address_dbid = await asyncio.gather(threads.run(token_dbid, row.token), threads.run(address_dbid, row['from']), threads.run(address_dbid, row['to']))
    # this addresses one tx with a crazy price due to yvpbtc v1 pricePerFullShare bug.
    price = row.price if len(str(round(row.price))) <= 20 else 99999999999999999999
    usd = row.value_usd if len(str(round(row.value_usd))) <= 20 else 99999999999999999999
    
    await threads.run(
        db_session(UserTx),
        chain=chain_pk,
        vault=vault_dbid,
        timestamp=row.timestamp,
        block=row.block,
        hash=row.hash,
        log_index=row.log_index,
        type=row.type,
        from_address=from_address_dbid,
        to_address=to_address_dbid,
        amount = row.amount,
        price = Decimal(price),
        value_usd = Decimal(usd),
        gas_used = row.gas_used,
        gas_price = row.gas_price,
    )

# Helper functions
async def get_token_transfers(token, start_block, end_block) -> pd.DataFrame:
    topics = construct_event_topic_set(
        filter_by_name('Transfer', token.abi)[0],
        web3.codec,
    )
    logs = await get_logs_asap(token.address, topics, from_block=start_block, to_block=end_block, sync=False)
    transfers = await asyncio.gather(*[_process_transfer_event(event) for event in decode_logs(logs)])
    return pd.DataFrame(transfers)


async def _process_transfer_event(event: _EventItem) -> dict:
    sender, receiver, amount = event.values()
    txhash = event.transaction_hash.hex()
    gas_price, gas_used, timestamp, token_dbid, price, scale = await asyncio.gather(
        _get_gas_price(txhash),
        _get_gas_used(txhash),
        get_block_timestamp_async(event.block_number),
        get_token_dbid(event.address),  # NOTE: we don't use this output but we call this to ensure the token fk is in the db before we insert the transfer
        get_price(event.address, event.block_number),
        ERC20(event.address, asynchronous=True).scale,
    )
    if (
        # NOTE magic.get_price() returns erroneous price due to erroneous ppfs
        chain.id == Network.Mainnet
        and event.address == '0x7F83935EcFe4729c4Ea592Ab2bC1A32588409797'
        and event.block_number == 12869164
    ):
        price = 99999

    amount = Decimal(amount) / scale
    price = Decimal(price)

    return {
        'chainid': chain.id,
        'block': event.block_number,
        'timestamp': int(timestamp),
        'hash': txhash,
        'log_index': event.log_index,
        'token': event.address,
        'type': _event_type(sender, receiver, event.address),
        'from': sender,
        'to': receiver,
        'amount': amount,
        'price': price,
        'value_usd': amount * price,
        'gas_used': gas_used,
        'gas_price': gas_price,
    }

@alru_cache(maxsize=None)
async def get_token_dbid(address: str) -> int:
    return await threads.run(token_dbid, address)

async def get_price(token_address, block):
    try:
        return await _get_price(token_address, block)
    except Exception as e:
        logger.warning(f'{e.__class__.__name__}: {str(e)}')
        logger.warning(f'vault: {token_address} block: {block}')
        raise e


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
    raise BatchSizeError(f'Stuck in infinite loop, increase transactions exporter batch size for {Network.name()}.')


class GasPriced(Struct):
    """This tiny struct allows us to only decode the gasPrice field and ignore the rest of the tx bytes."""
    gasPrice: uint

class GasUser(Struct):
    """This tiny struct allows us to only decode the gasUsed field and ignore the rest of the receipt bytes."""
    gasUsed: uint

@alru_cache(maxsize=1024)
async def _get_gas_price(txhash: str) -> int:
    tx_bytes = await dank_mids.eth._get_transaction_raw(txhash)
    return int(json.decode(tx_bytes, type=GasPriced, dec_hook=uint._decode_hook).gasPrice)

@alru_cache(maxsize=1024)
async def _get_gas_used(txhash: str) -> int:
    receipt_bytes = await dank_mids.eth._get_transaction_receipt_raw(txhash)
    return int(json.decode(receipt_bytes, type=GasUser, dec_hook=uint._decode_hook).gasUsed)