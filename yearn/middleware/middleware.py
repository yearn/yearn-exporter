import logging

import eth_retry
from brownie import web3 as w3
from eth_utils import encode_hex
from eth_utils import function_signature_to_4byte_selector as fourbyte
from requests import Session
from requests.adapters import HTTPAdapter
from web3 import HTTPProvider
from web3.middleware import filter
from y import Network
from y.constants import CHAINID

from yearn.cache import memory
from yearn.middleware import yearn_filter

logger = logging.getLogger(__name__)

PROVIDER_MAX_BATCH_SIZE = {
    "ankr":     500,
    "moralis":  2_000,
}

CHAIN_MAX_BATCH_SIZE = {
    Network.Mainnet: 10_000,  # 1.58 days
    Network.Gnosis: 20_000,  # 1.15 days
    Network.Fantom: 10_000,  # 0.1 days
    Network.Arbitrum: 20_000, # 0.34 days
    Network.Optimism: 800_000, # 10.02 days
    Network.Base: 800_000, # test value
}

def _get_batch_size() -> int:
    for provider, provider_max_batch_size in PROVIDER_MAX_BATCH_SIZE.items():
        if provider in w3.provider.endpoint_uri:
            return provider_max_batch_size
    return CHAIN_MAX_BATCH_SIZE[CHAINID]

BATCH_SIZE = _get_batch_size()

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
    return False


def cache_middleware(make_request, w3):
    @memory.cache
    def make_request_cached(method, params):
        return make_request(method, params)
    #make_request_cached = memory.cache(make_request)
    def middleware(method, params):
        logger.debug("%s %s", method, params)
        if should_cache(method, params):
            return make_request_cached(method, params)
        return make_request(method, params)
    return middleware


def catch_and_retry_middleware(make_request, w3):
    return eth_retry.auto_retry(make_request)


def setup_middleware():
    # patch web3 provider with more connections and higher timeout
    if w3.provider:
        assert w3.provider.endpoint_uri.startswith("http"), "only http and https providers are supported"
        adapter = HTTPAdapter(pool_connections=150, pool_maxsize=150)
        session = Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        w3.provider = HTTPProvider(w3.provider.endpoint_uri, {"timeout": 1800}, session)

        # patch and inject local filter middleware
        filter.MAX_BLOCK_REQUEST = BATCH_SIZE
        w3.middleware_onion.add(yearn_filter.local_filter_middleware)
        w3.middleware_onion.add(cache_middleware)
        w3.middleware_onion.add(catch_and_retry_middleware)
