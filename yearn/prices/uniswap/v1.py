from typing import Optional

from brownie import ZERO_ADDRESS, Contract, chain, interface
from brownie.exceptions import ContractNotFound
from cachetools.func import ttl_cache
from yearn.cache import memory
from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
from yearn.prices.constants import usdc
from yearn.utils import Singleton, contract

addresses = {
    Network.Mainnet: '0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95',
}

@memory.cache()
def _get_exchange(factory: Contract, token: str) -> str:
    """
    I extracted this fn for caching purposes.
    On-disk caching should be fine since no new pools should be added to uni v1
        which means a response equal to `ZERO_ADDRESS` implies there will never be a uni v1 pool for `token`.
    """
    return factory.getExchange(token)


class UniswapV1(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('uniswap v1 is not supported on this network')
        
        self.factory = contract(addresses[chain.id])

    def __contains__(self, asset):
        return chain.id in addresses

    @ttl_cache(ttl=600)
    def get_price(self, asset, block=None):
        try:
            asset = contract(asset)
            exchange = interface.UniswapV1Exchange(self.get_exchange(asset))
            eth_bought = exchange.getTokenToEthInputPrice(10 ** asset.decimals(), block_identifier=block)
            exchange = interface.UniswapV1Exchange(self.get_exchange(usdc))
            usdc_bought = exchange.getEthToTokenInputPrice(eth_bought, block_identifier=block) / 1e6
            fees = 0.997 ** 2
            return usdc_bought / fees
        except (ContractNotFound, ValueError) as e:
            pass
    
    def get_exchange(self, token: str) -> str:
        return _get_exchange(self.factory, token)
    
    def deepest_pool_balance(self, token_in: str, block: Optional[int] = None) -> int:
        exchange = self.get_exchange(token_in)
        if exchange == ZERO_ADDRESS:
            return None
        reserves = contract(token_in).balanceOf(exchange, block_identifier=block)
        return reserves


uniswap_v1 = None
try:
    uniswap_v1 = UniswapV1()
except UnsupportedNetwork:
    pass
