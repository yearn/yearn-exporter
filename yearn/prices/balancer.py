from brownie import Contract
from cachetools.func import ttl_cache

from yearn.cache import memory
from yearn.mutlicall import fetch_multicall
from yearn.prices import magic


@memory.cache()
def is_balancer_pool(address):
    pool = Contract(address)
    required = {"getCurrentTokens", "getBalance", "totalSupply"}
    if set(pool.__dict__) & required == required:
        return True
    return False


@ttl_cache(ttl=600)
def get_price(token, block=None):
    pool = Contract(token)
    tokens, supply = fetch_multicall([pool, "getCurrentTokens"], [pool, "totalSupply"], block=block)
    supply = supply / 1e18
    balances = fetch_multicall(*[[pool, "getBalance", token] for token in tokens], block=block)
    balances = [balance / 10 ** Contract(token).decimals() for balance, token in zip(balances, tokens)]
    total = sum(balance * magic.get_price(token, block=block) for balance, token in zip(balances, tokens))
    return total / supply
