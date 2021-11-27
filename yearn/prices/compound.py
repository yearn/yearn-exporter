from brownie import chain, Contract
from yearn.exceptions import UnsupportedNetwork
from yearn.utils import Singleton, contract
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
import logging

logger = logging.getLogger(__name__)


def get_fantom_ironbank():
    # HACK ironbank on fantom uses a non-standard proxy pattern
    unitroller = Contract('0x4250A6D3BD57455d7C6821eECb6206F507576cD2')
    implementation = Contract(unitroller.comptrollerImplementation())
    return Contract.from_abi(unitroller._name, str(unitroller), abi=implementation.abi)


addresses = {
    Network.Mainnet: {
        'compound': '0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B',
        'cream': '0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258',
        'ironbank': '0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB',
    },
    Network.Fantom: {
        'ironbank': get_fantom_ironbank,
    },
    Network.Arbitrum: {
        'ironbank': '0xbadaC56c9aca307079e8B8FC699987AAc89813ee',
    },
}


class Compound(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('compound is not supported on this network')

        results = fetch_multicall(
            *[
                [contract(addr) if isinstance(addr, str) else addr(), 'getAllMarkets']
                for addr in addresses[chain.id].values()
            ]
        )
        self.markets = dict(zip(addresses[chain.id], results))
        log_counts = ', '.join(
            f'{len(self.markets[name])} {name}' for name in self.markets
        )
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
