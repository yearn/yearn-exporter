import datetime
import logging

from brownie import chain, web3, Contract
from functools import lru_cache

from yearn.cache import memory

logger = logging.getLogger(__name__)


def safe_views(abi):
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
    header = web3.manager.request_blocking(f"erigon_getHeaderByNumber", [height])
    return int(header.timestamp, 16)


@memory.cache()
def closest_block_before_timestamp(timestamp):
    logger.info('closest block after timestamp %d', timestamp)
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if get_block_timestamp(mid) < timestamp:
            hi = mid
        else:
            lo = mid
    return hi if hi != height else None


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


@memory.cache()
def first_block_on_date(date_string):
    logger.info('first block on date %d', date_string)
    date = datetime.datetime.strptime(date_string, "%Y-%m-%d")
    date = date.date()
    previousdate = date - datetime.timedelta(days=1)
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if datetime.date.fromtimestamp(get_block_timestamp(mid)) > previousdate:
            hi = mid
        else:
            lo = mid
    return hi if hi != height else None
    

@memory.cache()
def last_block_on_date(date_string):
    logger.info('first block on date %d', date_string)
    date = datetime.datetime.strptime(date_string, "%Y-%m-%d")
    date = date.date()
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        print('block: ' + str(mid))
        print('mid: ' + str(datetime.date.fromtimestamp(get_block_timestamp(mid))))
        print(date)
        if datetime.date.fromtimestamp(get_block_timestamp(mid)) > date:
            hi = mid
        else:
            lo = mid
    hi = hi - 1
    return hi if hi != height else None


@memory.cache()
def contract_creation_block(address) -> int:
    """
    Find contract creation block using binary search.
    NOTE Requires access to historical state. Doesn't account for CREATE2 or SELFDESTRUCT.
    """
    logger.info("contract creation block %s", address)

    height = chain.height
    lo, hi = 0, height

    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if web3.eth.get_code(address, block_identifier=mid):
            hi = mid
        else:
            lo = mid

    return hi if hi != height else None


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


# Contract instance singleton, saves about 20ms of init time
contract = lru_cache(maxsize=None)(Contract)
