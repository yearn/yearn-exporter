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


@lru_cache(1)
def is_archive_node():
    return web3.clientVersion.startswith("TurboGeth")


def get_block_timestamp(height):
    if is_archive_node():
        header = web3.manager.request_blocking("tg_getHeaderByNumber", [height])
        return int(header.timestamp, 16)
    else:
        return chain[height].timestamp


@memory.cache()
def closest_block_after_timestamp(timestamp):
    logger.info('closest block after timestamp %d', timestamp)
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if get_block_timestamp(mid) > timestamp:
            hi = mid
        else:
            lo = mid
    return hi if hi != height else None


@memory.cache()
def contract_creation_block(address) -> int:
    """
    Determine the block when a contract was created.
    """
    logger.info("contract creation block %s", address)
    if is_archive_node():
        return _contract_creation_block_binary_search(address)
    else:
        return _contract_creation_block_bigquery(address)


def _contract_creation_block_binary_search(address):
    """
    Find contract creation block using binary search.
    NOTE Requires access to historical state. Doesn't account for CREATE2 or SELFDESTRUCT.
    """
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if web3.eth.getCode(address, block_identifier=mid):
            hi = mid
        else:
            lo = mid
    return hi if hi != height else None


def _contract_creation_block_bigquery(address):
    """
    Query contract creation block using BigQuery.
    NOTE Requires GOOGLE_APPLICATION_CREDENTIALS
         https://cloud.google.com/bigquery/docs/quickstarts/quickstart-client-libraries
    """
    from google.cloud import bigquery

    client = bigquery.Client()
    query = "select block_number from `bigquery-public-data.crypto_ethereum.contracts` where address = @address limit 1"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("address", "STRING", address.lower())]
    )
    query_job = client.query(query, job_config=job_config)
    for row in query_job:
        return row["block_number"]
