from brownie import web3
from joblib import Memory
import logging

from yearn.cache import memory
from eth_utils import encode_hex, function_signature_to_4byte_selector as fourbyte

logger = logging.getLogger(__name__)

CACHED_CALLS = [
    "name()",
    "symbol()",
    "decimals()",
]
CACHED_CALLS = [encode_hex(fourbyte(data)) for data in CACHED_CALLS]


def cache_middleware(make_request, w3):
    def middleware(method, params):
        should_cache = (
            method == "eth_call" and params[0]["data"] in CACHED_CALLS
            or method == "eth_getCode" and params[1] == "latest"
            or method == "eth_getLogs" and params[0]["toBlock"] - params[0]["fromBlock"] == 9999
        )
        logger.debug("%s  %s %s", "🔴🟢"[should_cache], method, params)
        if should_cache:
            response = memory.cache(make_request)(method, params)
        else:
            response = make_request(method, params)

        return response

    return middleware


def setup_middleware():
    from web3.middleware import filter

    filter.MAX_BLOCK_REQUEST = 10000
    web3.provider._request_kwargs["timeout"] = 600
    web3.middleware_onion.add(filter.local_filter_middleware)
    web3.middleware_onion.add(cache_middleware)
