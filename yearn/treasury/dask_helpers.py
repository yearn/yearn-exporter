import asyncio
import logging
import time
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import dask
from dask.delayed import Delayed
from eth_portfolio.buckets import get_token_bucket
from eth_portfolio.typing import (Balance, PortfolioBalances,
                                  RemoteTokenBalances, TokenBalances)
from y import ERC20, Network
from yearn.dask import use_chain_semaphore, CONCURRENCY
from y.exceptions import NonStandardERC20

from yearn.outputs.victoria.victoria import _build_item

logger = logging.getLogger(__name__)

"""
Distributed computing has some specific needs.
All objects must be picklable and special attention must be paid to import structure so objects can be correctly reassembled on the workers.
Hence this file.
"""

@lru_cache(1)
def _init_treasury():
    import eth_portfolio
    #from eth_portfolio import Portfolio # Fixes an import error
    from yearn.treasury.treasury import YearnTreasury
    return YearnTreasury(asynchronous=True)

@lru_cache(1)
def _init_sms():
    import eth_portfolio
    #from eth_portfolio import Portfolio # Fixes an import error
    from yearn.treasury.treasury import StrategistMultisig
    return StrategistMultisig(asynchronous=True)

@dask.delayed(name=f"describe treasury {Network.name()}", nout=2)
@use_chain_semaphore(CONCURRENCY)
async def describe_treasury(block: int) -> Tuple[PortfolioBalances, float]:
    # NOTE Don't refactor these together, the fn names are shown in dask. \/
    if block is None:
        return None, None
    start = time.time()
    data = await _init_treasury().describe(block)
    duration = time.time() - start
    return data, duration

@dask.delayed(name=f"describe sms {Network.name()}", nout=2)
@use_chain_semaphore(CONCURRENCY)
async def describe_sms(block: int) -> Tuple[PortfolioBalances, float]:
    # NOTE Don't refactor these together, the fn names are shown in dask. /\
    if block is None:
        return None, None
    start = time.time()
    data = await _init_sms().describe(block)
    duration = time.time() - start
    return data, duration

def treasury_data_for_export(block, timestamp):
    data, duration = describe_treasury(block)
    data = dask.delayed(_unpack_data_for_export, name="unpack treasury for export")("treasury", timestamp, data)
    return data, duration

def sms_data_for_export(block: Delayed, timestamp: Delayed) -> Delayed:
    data, duration = describe_sms(block)
    data = dask.delayed(_unpack_data_for_export, name=f"unpack sms for export")("sms", timestamp, data)
    return data, duration

async def _get_symbol(token):
    if token == 'ETH':
        return 'ETH'
    try:
        return await ERC20(token).symbol_async
    except NonStandardERC20:
        return None

async def _process_token(label: str, ts, section: str, wallet: str, token: str, bals: Balance, protocol: Optional[str] = None):
    # TODO wallet nicknames in grafana
    #wallet = KNOWN_ADDRESSES[wallet] if wallet in KNOWN_ADDRESSES else wallet
    if protocol is not None:
        wallet = f'{protocol} | {wallet}'

    symbol, bucket = await asyncio.gather(
        _get_symbol(token),
        get_token_bucket(token),
    )
    
    items = []           

    # build items
    for key, value in bals.items():
        label_names = ['param','wallet','token_address','token','bucket']
        if key == "usd_value":
            key = "usd value"
        label_values = [key, wallet, token, symbol, bucket]
        items.append(_build_item(f"{label}_{section}", label_names, label_values, value, ts))
    return items

@dask.delayed
async def _unpack_data_for_export(label: str, ts, data) -> List[Dict]:
    if data is None:
        return []
    try:
        metrics_to_export = []
        for wallet, wallet_data in data.items():
            for section, section_data in wallet_data.items():
                if isinstance(section_data, TokenBalances):
                    items = await asyncio.gather(*[
                        _process_token(label, ts, section, wallet, token, bals) for token, bals in section_data.items()
                    ])
                    for _items in items:
                        metrics_to_export.extend(_items)
                elif isinstance(section_data, RemoteTokenBalances):
                    if section == 'external':
                        section = 'assets'
                    for protocol, token_bals in section_data.items():
                        items = await asyncio.gather(*[
                            _process_token(label, ts, section, wallet, token, bals, protocol=protocol) for token, bals in token_bals.items()
                        ])
                        for _items in items:
                            metrics_to_export.extend(_items)
                else:
                    raise NotImplementedError()
    except Exception as e:
        logger.error(e)
        raise e
    return metrics_to_export