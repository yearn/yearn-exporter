from collections import Counter
from tabulate import tabulate
from brownie import web3
from web3 import middleware

stats = Counter()


def request_stats(make_request, w3):
    def middleware(method, params):
        print(method, params)
        stats[method] += 1
        response = make_request(method, params)
        return response

    return middleware


def display():
    print(tabulate(stats.most_common(), headers=["method", "count"]))


web3.middleware_onion.add(middleware.construct_simple_cache_middleware(dict, ["eth_getCode"]))
web3.middleware_onion.add(request_stats, "requests_stats")
