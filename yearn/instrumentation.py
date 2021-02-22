from collections import Counter

import click
from brownie import web3
from tabulate import tabulate

stats = Counter()


def request_stats(make_request, w3):
    def middleware(method, params):
        stats[method] += 1
        if method == "eth_call":
            print(".", end="", flush=True)
        response = make_request(method, params)
        return response

    return middleware


def enable():
    web3.middleware_onion.add(request_stats, "requests_stats")


def display():
    click.secho(f"{sum(stats.values())} calls", fg="yellow")
    print(tabulate(stats.most_common(), headers=["method", "count"]))
