from brownie import web3
from joblib import Memory
import logging

from yearn.cache import memory
from eth_utils import encode_hex, function_signature_to_4byte_selector as fourbyte

logger = logging.getLogger(__name__)

BATCH_SIZE = 10000
CACHED_CALLS = [
    "name()",
    "symbol()",
    "decimals()",
]
CACHED_CALLS = [encode_hex(fourbyte(data)) for data in CACHED_CALLS]


def should_cache(method, params):
    if method == "eth_call" and params[0]["data"] in CACHED_CALLS:
        return True
    if method == "eth_getCode" and params[1] == "latest":
        return True
    if method == "eth_getLogs":
        return int(params[0]["toBlock"], 16) - int(params[0]["fromBlock"], 16) == BATCH_SIZE - 1
    return False


def cache_middleware(make_request, w3):
    def middleware(method, params):
        logger.debug("%s %s", method, params)

        if should_cache(method, params):
            response = memory.cache(make_request)(method, params)
        else:
            response = make_request(method, params)

        return response

    return middleware


def setup_middleware():
    from web3.middleware import filter

    filter.MAX_BLOCK_REQUEST = BATCH_SIZE
    if web3.provider:
        web3.provider._request_kwargs["timeout"] = 600
    web3.middleware_onion.add(filter.local_filter_middleware)
    web3.middleware_onion.add(cache_middleware)
