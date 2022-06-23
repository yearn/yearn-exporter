from typing import Any, Literal, Optional, List
from brownie import chain
from cachetools.func import ttl_cache

from yearn.cache import memory
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.utils import contract, Singleton
from yearn.networks import Network
from yearn.typing import Address, Block
from yearn.exceptions import UnsupportedNetwork

networks = [ Network.Mainnet ]

@memory.cache()
def is_balancer_pool_cached(address: Address) -> bool:
    pool = contract(address)
    required = {"getCurrentTokens", "getBalance", "totalSupply"}
    return required.issubset(set(pool.__dict__))

class BalancerV1(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in networks:
            raise UnsupportedNetwork('Balancer is not supported on this network')

    def __contains__(self, token: Any) -> Literal[False]:
        return False

    def is_balancer_pool(self, address: Address) -> bool:
        return is_balancer_pool_cached(address)

    def get_version(self) -> str:
        return "v1"

    def get_tokens(self, token: Address) -> List:
        pool = contract(token)
        return pool.getCurrentTokens()

    @ttl_cache(ttl=600)
    def get_price(self, token: Address, block: Optional[Block] = None) -> float:
        pool = contract(token)
        tokens, supply = fetch_multicall([pool, "getCurrentTokens"], [pool, "totalSupply"], block=block)
        supply = supply / 1e18
        balances = fetch_multicall(*[[pool, "getBalance", token] for token in tokens], block=block)
        balances = [balance / 10 ** contract(token).decimals() for balance, token in zip(balances, tokens)]
        total = sum(balance * magic.get_price(token, block=block) for balance, token in zip(balances, tokens))
        return total / supply

balancer_v1 = None
try:
    balancer_v1 = BalancerV1()
except UnsupportedNetwork:
    pass
