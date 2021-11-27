from brownie import chain, interface
from brownie.exceptions import ContractNotFound
from cachetools.func import ttl_cache
from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
from yearn.prices.constants import usdc
from yearn.utils import Singleton, contract

addresses = {
    Network.Mainnet: '0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95',
}

class UniswapV1(metaclass=Singleton):
    def __init__(self, factory, router):
        if chain.id not in addresses:
            raise UnsupportedNetwork('uniswap v1 is not supported on this network')
        
        self.factory = contract(addresses[chain.id])

    @ttl_cache(ttl=600)
    def get_price(self, asset, block=None):
        try:
            asset = contract(asset)
            exchange = interface.UniswapV1Exchange(self.factory.getExchange(asset))
            eth_bought = exchange.getTokenToEthInputPrice(10 ** asset.decimals(), block_identifier=block)
            exchange = interface.UniswapV1Exchange(self.factory.getExchange(usdc))
            usdc_bought = exchange.getEthToTokenInputPrice(eth_bought, block_identifier=block) / 1e6
            fees = 0.997 ** 2
            return usdc_bought / fees
        except (ContractNotFound, ValueError) as e:
            pass


uniswap_v1 = None
try:
    uniswap_v1 = UniswapV1()
except UnsupportedNetwork:
    pass
