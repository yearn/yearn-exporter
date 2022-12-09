import asyncio
import logging
import warnings
from functools import lru_cache
from typing import List, NoReturn

import dask
import pandas
import sentry_sdk
from brownie import chain
from brownie.exceptions import BrownieEnvironmentWarning
from dask.delayed import Delayed
from pony.orm import TransactionIntegrityError, commit, db_session
from tqdm import tqdm
from y import Network, dank_w3
from y.constants import EEE_ADDRESS

from yearn.dask import ChainAwareClient, _get_async_client, _get_sync_client
from yearn.entities import TreasuryTx
from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                          cache_token)
from yearn.treasury import accountant
from yearn.treasury.treasury import YearnTreasury

sentry_sdk.set_tag('script','treasury_transactions_exporter')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logger = logging.getLogger('yearn.treasury_transactions_exporter')


def main() -> NoReturn:
    fn = export_treasury_txs
    _get_sync_client().submit(fn, key=f"{fn.__name__} {Network.name()}")

@lru_cache(maxsize=1)
def treasury_cached() -> YearnTreasury:
    return YearnTreasury(asynchronous=True, load_prices=True)

async def export_treasury_txs() -> NoReturn:
    treasury = treasury_cached()
    cached_thru = treasury._start_block - 1
    client: ChainAwareClient = await _get_async_client()
    while True:
        start_block = cached_thru + 1
        # NOTE: We look 50 blocks back to avoid uncles and reorgs
        end_block = await dank_w3.eth.block_number - 50
        if end_block < start_block:
            await asyncio.sleep(10)
            continue
            
        df = await treasury.ledger.df(start_block, end_block, full=True)
        if len(df) > 0:
            await client.compute(insert_delayed(df))
            #for index, row in tqdm(list(df.iterrows()), desc="Insert Txs to Postgres"):
            #    insert_treasury_tx(row)
            #sort()
        else:
            await asyncio.sleep(10)
        cached_thru = end_block

def insert_delayed(df: Delayed) -> Delayed:
    inserted = [dask.delayed(insert_treasury_tx)(row) for index, row in list(df.iterrows())]
    return sort_treasury_txs(inserted)

@dask.delayed
def sort_treasury_txs(_: List[Delayed]) -> None:
    # NOTE: we have the unused arg here so dask knows to collect all of the treasury txs before sorting.
    return sort()

@db_session
def insert_treasury_tx(row: pandas.Series) -> bool:
    block = row.blockNumber
    timestamp = chain[block].timestamp
    log_index = None if not hasattr(row, 'log_index') or str(row.log_index) in ["None", "nan"] else int(row.log_index)
    try:
        TreasuryTx(
            chain=cache_chain(),
            block = block,
            timestamp = timestamp,
            hash = row.hash,
            log_index = log_index,
            from_address = cache_address(row['from']),
            to_address = cache_address(row.to) if row.to and str(row.to) != "nan" else None,
            token = cache_token(row.token_address if hasattr(row, 'token_address') and row.token_address and str(row.token_address) != "nan" else EEE_ADDRESS),
            amount = row.value,
            price = row.price,
            value_usd = row.value_usd,
            gas_used = row.gasUsed if hasattr(row, 'gasUsed') and str(row.gasUsed) != "nan" else None,
            gas_price = row.gasPrice if hasattr(row, 'gasPrice') and str(row.gasPrice) != "nan" else None,
            txgroup = accountant.pending_txgroup(),
        )
        commit()
    except TransactionIntegrityError:
        _validate_integrity_error(row, log_index)

@db_session
def _validate_integrity_error(row, log_index: int) -> None:
    ''' Raises AssertionError if existing object that causes a TransactionIntegrityError is not an EXACT MATCH to the attempted insert. '''
    existing_object = TreasuryTx.get(hash=row.hash, log_index=log_index, chain=cache_chain())
    assert row['to'] == existing_object.to_address.address, (row['to'],existing_object.to_address.address)
    assert row['from'] == existing_object.from_address.address, (row['from'], existing_object.from_address.address)
    assert row['token_address'] == existing_object.token.address.address, (row['token_address'], existing_object.token.address.address)
    assert row['value'] == existing_object.amount, (row['value'], existing_object.amount)
    assert row['blockNumber'] == existing_object.block, (row['blockNumber'], existing_object.block)
    # NOTE All good!

@db_session
def sort() -> None:
    accountant.sort_txs(accountant.unsorted_txs())
