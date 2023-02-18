from typing import Any, Literal, Optional, List
from brownie import chain
from cachetools.func import ttl_cache

from yearn.cache import memory
from yearn.multicall2 import fetch_multicall
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

    def get_tokens(self, token: Address, block: Optional[Block] = None) -> List:
        pool = contract(token)
        pool_id = pool.getPoolId()
        vault = contract(pool.getVault())
        return vault.getPoolTokens(pool_id, block_identifier=block)[0]

    @ttl_cache(ttl=600)
    def get_price(self, token: Address, block: Optional[Block] = None) -> float:
        from yearn.prices import magic
        pool = contract(token)
        pool_id = pool.getPoolId()
        vault = contract(pool.getVault())
        tokens = vault.getPoolTokens(pool_id, block_identifier=block)
        balances = [balance for t, balance in zip(tokens[0], tokens[1]) if t != token]
        total = sum(balance * magic.get_price(t, block=block) for t, balance in zip(tokens[0], tokens[1]) if t != token)
        supply = sum(balances)
        return total / supply

balancer_v2 = None
try:
    balancer_v2 = BalancerV2()
except UnsupportedNetwork:
    pass
