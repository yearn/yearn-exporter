from brownie import chain
from cachetools.func import ttl_cache

from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
from yearn.utils import Singleton, contract, contract_creation_block
import logging

logger = logging.getLogger(__name__)

addresses = {
    Network.Mainnet: '0x5C08bC10F45468F18CbDC65454Cbd1dd2cB1Ac65',
}


class FixedForex(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork("fixed forex is not supported on this network")

        self.registry = contract(addresses[chain.id])
        self.registry_deploy_block = contract_creation_block(addresses[chain.id])
        self.markets = self.registry.forex()
        logger.info(f'loaded {len(self.markets)} fixed forex markets')

    def __contains__(self, token):
        return token in self.markets

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, token, block=None):
        if block is None or block >= self.registry_deploy_block:
            return self.registry.price(token, block_identifier=block) / 1e18
        else:
            # fallback method for before registry deployment
            oracle = contract(self.registry.oracle())
            ctoken = self.registry.cy(token)
            return oracle.getUnderlyingPrice(ctoken, block_identifier=block) / 1e18


fixed_forex = None
try:
    fixed_forex = FixedForex()
except UnsupportedNetwork:
    pass
