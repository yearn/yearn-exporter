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
    required = {"getVault", "getPoolId", "totalSupply"}
    return required.issubset(set(pool.__dict__))

class BalancerV2(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in networks:
            raise UnsupportedNetwork('Balancer is not supported on this network')

    def __contains__(self, token: Any) -> Literal[False]:
        return False

    def is_balancer_pool(self, address: Address) -> bool:
        return is_balancer_pool_cached(address)

    def get_version(self) -> str:
        return "v2"

    def get_tokens(self, token: Address) -> List:
        pool = contract(token)
        pool_id = pool.getPoolId()
        vault = contract(pool.getVault())
        return vault.getPoolTokens(pool_id)[0]

    @ttl_cache(ttl=600)
    def get_price(self, token: Address, block: Optional[Block] = None) -> float:
        pool = contract(token)
        pool_id = pool.getPoolId()
        vault = contract(pool.getVault())
        tokens, supply = fetch_multicall([vault, "getPoolTokens", pool_id], [pool, "totalSupply"], block=block)
        supply = supply / 1e18
        balances = [balance / 10 ** contract(token).decimals() for token, balance in zip(tokens[0], tokens[1])]
        total = sum(balance * magic.get_price(token, block=block) for token, balance in zip(tokens[0], tokens[1]))
        return total / supply

balancer_v2 = None
try:
    balancer_v2 = BalancerV2()
except UnsupportedNetwork:
    pass
