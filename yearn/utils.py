import logging

from brownie import chain, web3, Contract
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache

from yearn.cache import memory

logger = logging.getLogger(__name__)

class Direction(Enum):
    AFTER = 1
    BEFORE = -1

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


def closest_block_after_timestamp(timestamp):
    return timestamp_to_block(timestamp, Direction.AFTER)


def closest_block_before_timestamp(timestamp):
    return timestamp_to_block(timestamp, Direction.BEFORE)


def first_block_on_date(date_string):
    logger.info('first block on date %s', date_string)
    date = datetime.strptime(date_string, "%Y-%m-%d")
    timestamp = datetime.timestamp(date)
    return closest_block_after_timestamp(timestamp)


def last_block_on_date(date_string):
    logger.info('last block on date %s', date_string)
    date = datetime.strptime(date_string, "%Y-%m-%d")
    tomorrow = date + timedelta(days=1)
    timestamp = datetime.timestamp(tomorrow)
    return closest_block_before_timestamp(timestamp)


@memory.cache()
def timestamp_to_block(timestamp, direction):
    logger.debug('timestamp_to_block %d, direction %d', timestamp, direction)
    height = chain.height
    lo, hi = 0, height

    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if get_block_timestamp(mid) >= timestamp:
            hi = mid
        else:
            lo = mid

    if get_block_timestamp(hi) < timestamp:
        raise IndexError('timestamp is in the future')

    return hi if direction == Direction.AFTER else hi - 1


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
