import os
import logging
import threading
from functools import lru_cache
from typing import List

import eth_retry
from brownie import Contract, chain, convert, interface, web3
from brownie.exceptions import CompilerError
from time import time
from yearn.cache import memory
from yearn.exceptions import ArchiveNodeRequired, NodeNotSynced
from yearn.networks import Network
from yearn.typing import Address, AddressOrContract
from yearn.rpc_utils import CachedContract

logger = logging.getLogger(__name__)

BINARY_SEARCH_BARRIER = {
    Network.Mainnet: 0,
    Network.Gnosis: 15_659_482, # gnosis returns "No state available for block 0x3f9e020290502d1d41f4b5519e7d456f0935dea980ec310935206cac8239117e"
    Network.Fantom: 4_564_024,  # fantom returns "missing trie node" before that
    Network.Arbitrum: 0,
}

_erc20 = lru_cache(maxsize=None)(interface.ERC20)

PREFER_INTERFACE = {
    Network.Arbitrum: {
        "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f": _erc20, # empty ABI for WBTC when compiling the contract
    }
}

def safe_views(abi: List) -> List[str]:
    return [
        item["name"]
        for item in abi
        if item["type"] == "function"
        and item["stateMutability"] == "view"
        and not item["inputs"]
        and all(x["type"] in ["uint256", "bool"] for x in item["outputs"])
    ]


@memory.cache()
def get_block_timestamp(height):
    """
    An optimized variant of `chain[height].timestamp`
    """
    if chain.id == Network.Mainnet:
        header = web3.manager.request_blocking(f"erigon_getHeaderByNumber", [height])
        return int(header.timestamp, 16)
    else:
        return chain[height].timestamp


@memory.cache()
def closest_block_after_timestamp(timestamp):
    logger.debug('closest block after timestamp %d', timestamp)
    height = chain.height
    lo, hi = 0, height

    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if get_block_timestamp(mid) > timestamp:
            hi = mid
        else:
            lo = mid

    if get_block_timestamp(hi) < timestamp:
        raise IndexError('timestamp is in the future')

    return hi


def get_code(address, block=None):
    try:
        return web3.eth.get_code(address, block_identifier=block)
    except ValueError as exc:
        if isinstance(exc.args[0], dict) and 'missing trie node' in exc.args[0]['message']:
            raise ArchiveNodeRequired('querying historical state requires an archive node')
        raise exc


@memory.cache()
def contract_creation_block(address: AddressOrContract) -> int:
    """
    Find contract creation block using binary search.
    NOTE Requires access to historical state. Doesn't account for CREATE2 or SELFDESTRUCT.
    """
    logger.info("contract creation block %s", address)
    address = convert.to_address(address)

    barrier = BINARY_SEARCH_BARRIER[chain.id]
    lo = barrier
    hi = end = chain.height

    if hi == 0:
        raise NodeNotSynced(f'''
            `chain.height` returns 0 on your node, which means it is not fully synced.
            You can only use contract_creation_block on a fully synced node.''')

    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        try:
            code = get_code(address, block=mid)
        except ArchiveNodeRequired as exc:
            logger.error(exc)
            # with no access to historical state, we'll have to scan logs from start
            return 0
        except ValueError as exc:
            # ValueError occurs in gnosis when there is no state for a block
            # with no access to historical state, we'll have to scan logs from start
            logger.error(exc) 
            return 0
        if code:
            hi = mid
        else:
            lo = mid

    # only happens on fantom
    if hi == barrier + 1:
        logger.warning('could not determine creation block for a contract deployed prior to barrier')
        return 0

    return hi if hi != end else None


# cached Contract instance, saves about 20ms of init time
_contract_lock = threading.Lock()
_contract = lru_cache(maxsize=None)(Contract)
_cached_contract = lru_cache(maxsize=None)(CachedContract)

@eth_retry.auto_retry
def contract(address: Address) -> Contract:
    with _contract_lock:
        if chain.id in PREFER_INTERFACE:
            if address in PREFER_INTERFACE[chain.id]:
                _interface = PREFER_INTERFACE[chain.id][address]
                i = _interface(address)
                return _squeeze(i)

        failed_attempts = 0
        while True:
            start = time()
            try:
                if os.getenv("HASH_BROWNIE_HOST"):
                    c = _cached_contract(address)
                else:
                    c = _contract(address)

                logger.debug("loaded contract %s in %.3fms", address, (time()-start)*1E3)
                return _squeeze(c)

            except (AssertionError, CompilerError) as e:
                if failed_attempts == 3:
                    raise
                logger.warning(e)
                Contract.remove_deployment(address)
                failed_attempts += 1


@lru_cache(maxsize=None)
def is_contract(address: str) -> bool:
    '''checks to see if the input address is a contract'''
    return web3.eth.get_code(address) not in ['0x',b'']


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _squeeze(it):
    """ Reduce the contract size in RAM significantly. """
    for k in ["ast", "bytecode", "coverageMap", "deployedBytecode", "deployedSourceMap", "natspec", "opcodes", "pcMap"]:
        if it._build and k in it._build.keys():
            it._build[k] = {}
    return it
