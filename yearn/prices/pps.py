from brownie import chain

from cachetools.func import ttl_cache
from yearn.utils import Singleton
from yearn.networks import Network
from yearn.exceptions import UnsupportedNetwork
from yearn.utils import contract
import yearn.prices.magic as magic
import logging

logger = logging.getLogger(__name__)


networks = [ Network.Mainnet, Network.Fantom, Network.Arbitrum ]
assets = {
    Network.Mainnet: {
      "0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab": 12429262,
    }
}

class PricePerShare(metaclass=Singleton):
    def __init__(self):
        if chain.id not in networks:
            raise UnsupportedNetwork('pps is not supported on this network')


    def token_wants_pps_price(self, asset, block=None):
        if asset not in assets[chain.id].keys():
            return False

        base_block = next(iter(assets[chain.id][asset]))
        if not block or not base_block:
            # "0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab": None
            # *always* use the pps logic
            return True
        else:
            # "0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab": 12429262
            # check if the pps logic should be used based on the given block
            return block <= base_block


    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, asset, block=None):
        base_block = next(iter(assets[chain.id][asset]))
        if not base_block:
            base_block = block

        try:
            asset_contract = contract(asset)
            decimals = asset_contract.decimals()
            ppfs = asset_contract.getPricePerFullShare(block_identifier=base_block) / 10**decimals
            underlying = asset_contract.token()
            want_price = magic.get_price(underlying, block=block)
            return ppfs * want_price
        except ValueError as e:
            logger.error(e)
            return None


pps = None
try:
    pps = PricePerShare()
except UnsupportedNetwork:
    pass
