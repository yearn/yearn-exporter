from functools import cached_property
from typing import ChainMap
from brownie import chain
from yearn.utils import Singleton, contract
from yearn.multicall2 import fetch_multicall
from cachetools.func import ttl_cache
from typing import Optional
from yearn.exceptions import UnsupportedNetwork


address_providers = {
    1: {
        'v1': '0x24a42fD28C976A61Df5D00D0599C34c4f90748c8',
        'v2': '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5',
    }
}


class Aave(metaclass=Singleton):
    def __init__(self):
        if chain.id not in address_providers:
            raise UnsupportedNetwork("aave is not supported on this network")

    def atoken_underlying(self, atoken: str) -> Optional[str]:
        return self.markets.get(atoken)

    @property
    def markets(self):
        return ChainMap(self.v2_markets, self.v1_markets)

    @cached_property
    def v2_markets(self):
        # atoken -> token
        address_provider = contract(address_providers[chain.id]['v2'])
        lending_pool = contract(address_provider.getLendingPool())
        tokens = lending_pool.getReservesList()
        markets = fetch_multicall(
            *[[lending_pool, 'getReserveData', token] for token in tokens]
        )
        return {
            market['aTokenAddress']: token for token, market in zip(tokens, markets)
        }

    @cached_property
    def v1_markets(self):
        # atoken -> token
        address_provider = contract(address_providers[chain.id]['v1'])
        lending_pool = contract(address_provider.getLendingPool())
        tokens = lending_pool.getReserves()
        markets = fetch_multicall(
            *[[lending_pool, 'getReserveData', token] for token in tokens]
        )
        return {
            market['aTokenAddress']: token for token, market in zip(tokens, markets)
        }


try:
    aave = Aave()
except UnsupportedNetwork:
    aave = None
