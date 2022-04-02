import logging
from functools import lru_cache
import threading
from typing import List

from brownie import Contract, chain, web3, interface

from yearn.cache import memory
from yearn.exceptions import ArchiveNodeRequired
from yearn.networks import Network
from yearn.typing import Address

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
def contract_creation_block(address) -> int:
    """
    Find contract creation block using binary search.
    NOTE Requires access to historical state. Doesn't account for CREATE2 or SELFDESTRUCT.
    """
    logger.info("contract creation block %s", address)

    barrier = BINARY_SEARCH_BARRIER[chain.id]
    lo = barrier
    hi = end = chain.height

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


class Singleton(type):
    def __init__(self, *args, **kwargs):
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
            return self.__instance
        else:
            return self.__instance


# cached Contract instance, saves about 20ms of init time
_contract_lock = threading.Lock()
_contract = lru_cache(maxsize=None)(Contract)

def contract(address: Address) -> Contract:
    with _contract_lock:
        if chain.id in PREFER_INTERFACE:
            if address in PREFER_INTERFACE[chain.id]:
                _interface = PREFER_INTERFACE[chain.id][address]
                return _interface(address)

        return _contract(address)


def is_contract(address: str) -> bool:
    '''checks to see if the input address is a contract'''
    return web3.eth.get_code(address) != '0x'


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]