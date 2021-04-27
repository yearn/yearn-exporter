import logging

from brownie import web3 as w3
from eth_utils import encode_hex
from eth_utils import function_signature_to_4byte_selector as fourbyte
from requests import Session
from requests.adapters import HTTPAdapter
from web3 import HTTPProvider
from web3.middleware import filter

from yearn.cache import memory

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
    # patch web3 provider with more connections and higher timeout
    assert w3.provider.endpoint_uri.startswith("http"), "only http and https providers are supported"
    adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    w3.provider = HTTPProvider(w3.provider.endpoint_uri, {"timeout": 600}, session)

    # patch and inject local filter middleware
    filter.MAX_BLOCK_REQUEST = BATCH_SIZE
    w3.middleware_onion.add(filter.local_filter_middleware)
    w3.middleware_onion.add(cache_middleware)
