import logging

import eth_retry
from brownie import chain
from brownie import web3 as w3
from eth_utils import encode_hex
from eth_utils import function_signature_to_4byte_selector as fourbyte
from requests import Session
from requests.adapters import HTTPAdapter
from web3 import HTTPProvider
from web3.middleware import filter
from yearn.cache import memory
from yearn.middleware import yearn_filter
from yearn.networks import Network
from yearn.rpc_utils import HashBrownieClient, cached_logs

logger = logging.getLogger(__name__)

BATCH_SIZE = {
    Network.Mainnet: 10_000,  # 1.58 days
    Network.Gnosis: 20_000,  # 1.15 days
    Network.Fantom: 100_000,  # 1.03 days
    Network.Arbitrum: 20_000, # 0.34 days
}
CACHED_CALLS = [
    "name()",
    "symbol()",
    "decimals()",
]
CACHED_CALLS = [encode_hex(fourbyte(data)) for data in CACHED_CALLS]


def get_cache_processor(make_request, method, params):
    hb = HashBrownieClient()
    if hb.get_client() and hb.supports_method(method):
        return hb.get_rpc_processor

    # do the previous disk-based caching
    if method == "eth_call" and params[0]["data"] in CACHED_CALLS:
        return memory.cache(make_request)
    elif method == "eth_getCode" and params[1] == "latest":
        return memory.cache(make_request)
    elif method == "eth_getLogs" and int(params[0]["toBlock"], 16) - int(params[0]["fromBlock"], 16) == BATCH_SIZE[chain.id] - 1:
        return memory.cache(make_request)
    return None


def cache_middleware(make_request, w3):
    def middleware(method, params):
        logger.debug("%s %s", method, params)

        cache_processor = get_cache_processor(make_request, method, params)
        if cache_processor:
            response = cache_processor(method, params)
        else:
            response = make_request(method, params)

        return response

    return middleware


def catch_and_retry_middleware(make_request, w3):

    @eth_retry.auto_retry
    def middleware(method, params):
        return make_request(method, params)

    return middleware


def setup_middleware():
    # patch web3 provider with more connections and higher timeout
    if w3.provider:
        assert w3.provider.endpoint_uri.startswith("http"), "only http and https providers are supported"
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
        session = Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        w3.provider = HTTPProvider(w3.provider.endpoint_uri, {"timeout": 600}, session)

        # patch and inject local filter middleware
        filter.MAX_BLOCK_REQUEST = BATCH_SIZE[chain.id]
        w3.middleware_onion.add(yearn_filter.local_filter_middleware)
        w3.middleware_onion.add(cache_middleware)
        w3.middleware_onion.add(catch_and_retry_middleware)
