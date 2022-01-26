from brownie import Contract, chain
from cachetools.func import ttl_cache

from yearn.cache import memory
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.utils import contract, Singleton
from yearn.networks import Network
from yearn.exceptions import UnsupportedNetwork

networks = [ Network.Mainnet ]

@memory.cache()
def is_balancer_pool_cached(address):
    pool = contract(address)
    required = {"getCurrentTokens", "getBalance", "totalSupply"}
    if set(pool.__dict__) & required == required:
        return True
    return False

class Balancer(metaclass=Singleton):
    def __init__(self):
        if chain.id not in networks:
            raise UnsupportedNetwork('Balancer is not supported on this network')

    def __contains__(self, token):
        return False

    def is_balancer_pool(self, address):
        return is_balancer_pool_cached(address)

    @ttl_cache(ttl=600)
    def get_price(self, token, block=None):
        pool = contract(token)
        tokens, supply = fetch_multicall([pool, "getCurrentTokens"], [pool, "totalSupply"], block=block)
        supply = supply / 1e18
        balances = fetch_multicall(*[[pool, "getBalance", token] for token in tokens], block=block)
        balances = [balance / 10 ** contract(token).decimals() for balance, token in zip(balances, tokens)]
        total = sum(balance * magic.get_price(token, block=block) for balance, token in zip(balances, tokens))
        return total / supply

balancer = None
try:
    balancer = Balancer()
except UnsupportedNetwork:
    pass
