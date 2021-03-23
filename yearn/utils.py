import logging
from brownie import chain, web3
from cachetools.func import lru_cache

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
def contract_creation_block(address) -> int:
    """
    Use binary search to determine the block when a contract was created.
    NOTE Requires access to archive state. A recommended option is Turbo Geth.

    TODO Add fallback to BigQuery
    """
    logger.info("contract creation block %s", address)
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if web3.eth.getCode(address, block_identifier=mid):
            hi = mid
        else:
            lo = mid
    return hi if hi != height else None
