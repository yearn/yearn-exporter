from brownie import web3
from joblib import Memory


def cache_middleware(make_request, w3):
    memory = Memory("cache", verbose=0)

    def middleware(method, params):
        should_cache = (
            method == "eth_getCode" or
            method == "eth_getLogs" and params[0]["toBlock"] - params[0]["fromBlock"] == 9999
        )
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
