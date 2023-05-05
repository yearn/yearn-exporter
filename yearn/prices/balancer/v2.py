from typing import Any, List, Literal, Optional

from brownie import chain
from cachetools.func import ttl_cache
from y import Contract, Network

from yearn.cache import memory
from yearn.exceptions import UnsupportedNetwork
from yearn.prices import magic
from yearn.typing import Address, Block
from yearn.utils import Singleton

networks = [ Network.Mainnet ]

@memory.cache()
def is_balancer_pool_cached(address: Address) -> bool:
    pool = Contract(address)
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
        pool = Contract(token)
        pool_id = pool.getPoolId()
        vault = Contract(pool.getVault())
        return vault.getPoolTokens(pool_id, block_identifier=block)[0]

    @ttl_cache(ttl=600)
    def get_price(self, token: Address, block: Optional[Block] = None) -> float:
        pool = Contract(token)
        pool_id = pool.getPoolId()
        vault = Contract(pool.getVault())
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
