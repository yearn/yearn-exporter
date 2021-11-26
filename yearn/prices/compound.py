from brownie import chain
from yearn.exceptions import UnsupportedNetwork
from yearn.utils import Singleton, contract
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
import logging

logger = logging.getLogger(__name__)


addresses = {
    Network.Mainnet: {
        'compound': '0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B',
        'cream': '0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258',
        'ironbank': '0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB',
    }
}


class Compound(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('compound is not supported on this network')

        results = fetch_multicall(*[
            [contract(addr), 'getAllMarkets']
            for addr in addresses[chain.id].values()
        ])
        self.markets = dict(zip(addresses[chain.id], results))
        log_counts = ', '.join(f'{len(self.markets[name])} {name}' for name in self.markets)
        logger.info(f'loaded {log_counts} markets')

    def __contains__(self, token):
        return any(token in market for market in self.markets.values())

    def get_price(self, token, block=None):
        token = contract(token)
        underlying, exchange_rate, decimals = fetch_multicall(
            [token, 'underlying'],
            [token, 'exchangeRateCurrent'],
            [token, 'decimals'],
            block=block,
        )
        exchange_rate /= 1e18
        under_decimals = contract(underlying).decimals()
        return [exchange_rate * 10 ** (decimals - under_decimals), underlying]


compound = None
try:
    compound = Compound()
except UnsupportedNetwork:
    pass
