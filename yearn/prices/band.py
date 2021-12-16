from functools import cached_property
from brownie import chain

from cachetools.func import ttl_cache
from yearn.utils import Singleton
from yearn.networks import Network
from yearn.exceptions import UnsupportedNetwork
from yearn.utils import contract


addresses = {
    # https://docs.fantom.foundation/tutorials/band-protocol-standard-dataset
    Network.Fantom: '0x56E2898E0ceFF0D1222827759B56B28Ad812f92F'
}

class Band(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('band is not supported on this network')
        self.oracle = contract(addresses[chain.id])

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, asset, block=None):
        asset_symbol = contract(asset).symbol()
        try:
            return self.oracle.getReferenceData(asset_symbol, 'USDC', block_identifier=block)[0] / 1e18
        except ValueError:
            return None


band = None
try:
    band = Band()
except UnsupportedNetwork:
    pass
