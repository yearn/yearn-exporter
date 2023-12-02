import asyncio
import logging
import time
import warnings
from typing import NoReturn

import sentry_sdk
from a_sync import AsyncThreadPoolExecutor, a_sync
from a_sync.utils.iterators import _Done
from brownie import chain
from brownie.exceptions import BrownieEnvironmentWarning
from eth_portfolio.structs import (InternalTransfer, LedgerEntry,
                                   TokenTransfer, Transaction)
from pony.orm import TransactionIntegrityError, commit, db_session
from tqdm.asyncio import tqdm_asyncio
from y.constants import EEE_ADDRESS
from y.datatypes import Block
from y.time import get_block_timestamp_async

from yearn.entities import TreasuryTx, deduplicate_internal_transfers
from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                          cache_token)
from yearn.treasury import accountant
from yearn.treasury.treasury import YearnTreasury

sentry_sdk.set_tag('script','treasury_transactions_exporter')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logger = logging.getLogger('yearn.treasury_transactions_exporter')

treasury = YearnTreasury(load_prices=True, asynchronous=True)


def main() -> NoReturn:
    cached_thru = treasury._start_block - 1
    while True:
        start_block = cached_thru + 1
        # NOTE: We look 50 blocks back to avoid uncles and reorgs
        end_block = chain.height - 50
        if end_block < start_block:
            time.sleep(10)
            continue
            
        to_sort = load_new_txs(start_block, end_block)
        deduplicate_internal_transfers()
        if to_sort > 0:
            sort()
        else:
            time.sleep(10)
        cached_thru = end_block


@a_sync(default='sync')
async def load_new_txs(start_block: Block, end_block: Block) -> int:
    """returns: number of new txs"""
    futs = [
        asyncio.create_task(insert_treasury_tx(entry))
        async for entry in treasury.ledger._get_and_yield(start_block, end_block)
        if not isinstance(entry, _Done) and entry.value
    ]
    if not futs:
        return 0
    to_sort = sum(await tqdm_asyncio.gather(*futs, desc="Insert Txs to Postgres"))
    return to_sort



# NOTE: Things get sketchy when we bump these higher
insert_thread = AsyncThreadPoolExecutor(1)
sort_thread = AsyncThreadPoolExecutor(1)

# NOTE: These we need to sort later for reasons I no longer remember
sort_later = lambda entry: isinstance(entry, TokenTransfer)

async def insert_treasury_tx(entry: LedgerEntry) -> int:
    ts = int(await get_block_timestamp_async(entry.block_number))
    if txid := await insert_thread.run(insert_to_db, entry, ts):
        if sort_later(entry):
            return 1
        await sort_thread.run(accountant.sort_tx, txid)
    return 0

    
@db_session
def insert_to_db(entry: LedgerEntry, ts: int) -> bool:
    if isinstance(entry, TokenTransfer):
        log_index = entry.log_index
        token = cache_token(entry.token_address)
        gas = None
    else:
        log_index = None
        token = cache_token(EEE_ADDRESS)
        gas = entry.gas
    try:
        entity = TreasuryTx(
            chain=cache_chain(),
            block = entry.block_number,
            timestamp = ts,
            hash = entry.hash,
            log_index = log_index,
            from_address = cache_address(entry.from_address) if entry.from_address else None,
            to_address = cache_address(entry.to_address) if entry.to_address else None,
            token = token,
            amount = entry.value,
            price = entry.price,
            value_usd = entry.value_usd,
            # TODO: nuke db and add this column
            # gas = gas,
            gas_used = entry.gas_used if isinstance(entry, InternalTransfer) else None,
            gas_price = entry.gas_price if isinstance(entry, Transaction) else None,
            txgroup = accountant.pending_txgroup(),
        )
        commit()
        return entity.treasury_tx_id
    except TransactionIntegrityError:
        _validate_integrity_error(entry, log_index)


@db_session
def _validate_integrity_error(entry: LedgerEntry, log_index: int) -> None:
    ''' Raises AssertionError if existing object that causes a TransactionIntegrityError is not an EXACT MATCH to the attempted insert. '''
    existing_object = TreasuryTx.get(hash=entry.hash, log_index=log_index, chain=cache_chain())
    if existing_object is None:
        existing_objects = list(TreasuryTx.select(lambda tx: tx.hash==entry.hash and tx.log_index==log_index and tx.chain==cache_chain()))
        raise ValueError(f'unable to `.get` due to multiple entries: {existing_objects}')
    assert entry.to_address == existing_object.to_address.address, (entry.to_address,existing_object.to_address.address)
    assert entry.from_address == existing_object.from_address.address, (entry.from_address, existing_object.from_address.address)
    assert entry.value == existing_object.amount or entry.value == -1 * existing_object.amount, (entry.value, existing_object.amount)
    assert entry.block_number == existing_object.block, (entry.block_number, existing_object.block)
    if isinstance(entry, TokenTransfer):
        assert entry.token_address == existing_object.token.address.address, (entry.token_address, existing_object.token.address.address)
    else:
        assert existing_object.token.address.address == EEE_ADDRESS
    # NOTE All good!

@db_session
def sort() -> None:
    accountant.sort_txs(accountant.unsorted_txs())
