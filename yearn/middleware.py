import os

from brownie import web3
from joblib import Memory


def cache_logs_middleware(make_request, w3):
    memory = Memory("cache", verbose=0)

    def middleware(method, params):
        if method == "eth_getLogs":
            if params[0]["toBlock"] - params[0]["fromBlock"] == 9999:
                return memory.cache(make_request)(method, params)
            else:
                print("no cache", method, params)
        return make_request(method, params)

    return middleware


def setup_middleware():
    os.environ["WEB3_MAX_BLOCK_REQUEST"] = str(10000)
    from web3.middleware.filter import local_filter_middleware

    web3.provider._request_kwargs["timeout"] = 600
    web3.middleware_onion.add(local_filter_middleware)
    web3.middleware_onion.add(cache_logs_middleware)
