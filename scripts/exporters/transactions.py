import asyncio
import logging
import time
import warnings
from decimal import Decimal
from functools import lru_cache
from typing import List, Literal, NoReturn, Optional

import dask
import pandas as pd
import sentry_sdk
from brownie import ZERO_ADDRESS, chain, web3
from brownie.exceptions import BrownieEnvironmentWarning
from dask.distributed import Future
from multicall.utils import await_awaitable
from pony.orm import db_session
from web3.datastructures import AttributeDict
from y.networks import Network
from y.utils.events import get_logs_asap_async, get_logs_asap_generator

from yearn.constants import ERC20_TRANSFER_EVENT_HASH
from yearn.dask import _get_async_client, _get_sync_client
from yearn.entities import UserTx
from yearn.events import decode_logs
from yearn.exceptions import BatchSizeError
from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                          cache_token, last_recorded_block)
from yearn.prices.magic import _get_price
from yearn.typing import Block
from yearn.utils import run_in_thread
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','transactions_exporter')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)



logger = logging.getLogger('yearn.transactions_exporter')

BATCH_SIZE = {
    Network.Mainnet: 5_000,
    Network.Fantom: 20_000,
    Network.Gnosis: 2_000_000,
    Network.Arbitrum: 1_000_000,
    Network.Optimism: 4_000_000,
}[chain.id]

FIRST_END_BLOCK = {
    Network.Mainnet: 9_480_000, # NOTE block some arbitrary time after iearn's first deployment
    Network.Fantom: 5_000_000, # NOTE block some arbitrary time after v2's first deployment
    Network.Gnosis: 21_440_000, # # NOTE block some arbitrary time after first vault deployment
    Network.Arbitrum: 4_837_859,
    Network.Optimism: 18_111_485,
}[chain.id]


'''
def main():
    _cached_thru_from_last_run = 0
    while True:
        cached_thru = last_recorded_block(UserTx)
        _check_for_infinite_loop(_cached_thru_from_last_run, cached_thru)
        process_and_cache_user_txs(cached_thru)
        _cached_thru_from_last_run = cached_thru
        time.sleep(1) # No need to waste compute
'''

@lru_cache(1)
def _get_yearn() -> Yearn:
    return Yearn()

def active_vaults_at(block: int):
    return _get_yearn().active_vaults_at(block)

futs: List[Future] = []
def main():
    client = _get_sync_client()
    tokens_with_futs = []
    while True:
        active_vaults_fut = client.submit(active_vaults_at, chain.height)
        while not active_vaults_fut.status in ["finished", "error"]:
            time.sleep(1)
        tokens = fut.result() - tokens_with_futs
        futs.extend(client.compute(export_user_transactions_for_token(str(vault), vault.name) for vault in tokens))
        tokens_with_futs.extend(tokens)
        for fut in futs:
            if fut.status == "error":
                raise fut.exception()
        # NOTE: After 10 minutes, we will check for new vaults and submit additional dask Futures as necessary.
        time.sleep(600)

@dask.delayed
async def export_user_transactions_for_token(token: str, name: str) -> NoReturn:
    client = await _get_async_client()
    token_futs: List[Future] = []
    async for logs in get_logs_asap_generator(token, [ERC20_TRANSFER_EVENT_HASH], run_forever=True):
        if logs:
            decoded = await run_in_thread(decode_logs, logs)
            enriched = [dask.delayed(_process_transfer_event)(event) for event in decoded]
            futs_for_batch = client.compute([export_user_transfer(transfer) for transfer in enriched], asynchronous=True)
            token_futs.append(client.gather(futs_for_batch, asynchronous=True))
        
        for i, fut in enumerate(token_futs):
            if fut.status == "error":
                raise fut.exception()
            if fut.status == "finished":
                results = await futs.pop(i)
                first_block = min(results)
                last_block = max(results)
                block_string = f"[block {first_block}]" if first_block == last_block else f"[blocks {first_block}-{last_block}]"
                logger.info(f'{len(results)} {Network.name()} {name} user txs exported to postrges {block_string}')
            

@db_session
def process_and_cache_user_txs(last_saved_block: Optional[int] = None) -> None:
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
    vaults = await_awaitable(yearn.active_vaults_at(end_block))
    if not vaults:
        return
    futs = client.compute([get_user_transfers(vault.vault, start_block, end_block) for vault in vaults], asynchronous=True)
    df = pd.concat(client.gather(futs))
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

@dask.delayed
@db_session
def export_user_transfer(data: dict) -> Literal[1]:
    # this addresses one tx with a crazy price due to yvpbtc v1 pricePerFullShare bug.
    price = data.price if len(str(round(data.price))) <= 20 else 99999999999999999999
    usd = data.value_usd if len(str(round(data.value_usd))) <= 20 else 99999999999999999999
    chain = cache_chain()
    if not UserTx.get(chain=chain, hash=data.hash, log_index=data.log_index):
        UserTx(
            chain=chain,
            vault=cache_token(data.token),
            timestamp=data.timestamp,
            block=data.block,
            hash=data.hash,
            log_index=data.log_index,
            type=data.type,
            from_address=cache_address(data['from']),
            to_address=cache_address(data['to']),
            amount = data.amount,
            price = price,
            value_usd = usd,
            gas_used = data.gas_used,
            gas_price = data.gas_price
        )
    return data.block


# Helper functions
@dask.delayed
async def get_user_transfers(token, start_block, end_block) -> pd.DataFrame:
    logs = await get_logs_asap_async(token.address, [ERC20_TRANSFER_EVENT_HASH], from_block=start_block, to_block=end_block)
    decoded = await run_in_thread(decode_logs, logs)
    token_entity = cache_token(token.address)
    transfers = await asyncio.gather(*[_process_transfer_event(event, token_entity) for event in decoded])
    return pd.DataFrame(transfers)

@db_session
async def _process_transfer_event(event) -> dict:
    sender, receiver, amount = event.values()
    cache_address(sender)
    cache_address(receiver)
    token = cache_token(event.address)
    price = await get_price(token.address.address, event.block_number)
    if (
        # NOTE magic.get_price() returns erroneous price due to erroneous ppfs
        token.address.address == '0x7F83935EcFe4729c4Ea592Ab2bC1A32588409797'
        and event.block_number == 12869164
    ):
        price = 99999
    txhash = event.transaction_hash.hex()
    return AttributeDict({
        'chainid': chain.id,
        'block': event.block_number,
        'timestamp': chain[event.block_number].timestamp,
        'hash': txhash,
        'log_index': event.log_index,
        'token': token.address.address,
        'type': _event_type(sender, receiver, token.address.address),
        'from': sender,
        'to': receiver,
        'amount': Decimal(amount) / Decimal(10 ** token.decimals),
        'price': price,
        'value_usd': Decimal(amount) / Decimal(10 ** token.decimals) * Decimal(price),
        'gas_used': web3.eth.getTransactionReceipt(txhash).gasUsed,
        'gas_price': web3.eth.getTransaction(txhash).gasPrice
    })


async def get_price(token_address, block):
    try:
        return await _get_price(token_address, block)
    except Exception as e:
        logger.warn(f'{e.__class__.__name__}: {str(e)}')
        logger.warn(f'vault: {token_address} block: {block}')
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
    raise BatchSizeError(f'Stuck in infinite loop, increase transactions exporter batch size for {Network(chain.id).name}.')
