from functools import lru_cache
from typing import Any, Optional

from brownie import ZERO_ADDRESS, Contract, chain, interface
from brownie.convert.datatypes import EthAddress
from brownie.exceptions import ContractNotFound
from cachetools.func import ttl_cache
from y.networks import Network

from yearn.exceptions import UnsupportedNetwork
from yearn.prices.constants import usdc
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import Singleton, contract

addresses = {
    Network.Mainnet: '0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95',
}

@lru_cache
def _get_exchange(factory: Contract, token: AddressOrContract) -> EthAddress:
    """
    I extracted this fn for caching purposes.
    On-disk caching should be fine since no new pools should be added to uni v1
        which means a response equal to `ZERO_ADDRESS` implies there will never be a uni v1 pool for `token`.
    """
    return factory.getExchange(token)


class UniswapV1(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in addresses:
            raise UnsupportedNetwork('uniswap v1 is not supported on this network')
        
        self.factory = contract(addresses[chain.id])

    def __contains__(self, asset: Any) -> bool:
        return chain.id in addresses

    @ttl_cache(ttl=600)
    def get_price(self, asset: Address, block: Optional[Block] = None) -> Optional[float]:
        try:
            asset = contract(asset)
            exchange = interface.UniswapV1Exchange(self.get_exchange(asset))
            eth_bought = exchange.getTokenToEthInputPrice(10 ** asset.decimals(), block_identifier=block)
            exchange = interface.UniswapV1Exchange(self.get_exchange(usdc))
            usdc_bought = exchange.getEthToTokenInputPrice(eth_bought, block_identifier=block) / 1e6
            fees = 0.997 ** 2
            return usdc_bought / fees
        except (ContractNotFound, ValueError) as e:
            return None
    
    def get_exchange(self, token: AddressOrContract) -> EthAddress:
        return _get_exchange(self.factory, token)
    
    def deepest_pool_balance(self, token_in: Address, block: Optional[Block] = None) -> int:
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
