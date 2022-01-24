import logging

from brownie import chain
from cachetools.func import lru_cache, ttl_cache
from eth_abi import encode_single

from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)

addresses = {
    Network.Mainnet: '0x823bE81bbF96BEc0e25CA13170F5AaCb5B79ba83',
}


class Synthetix(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork("synthetix is not supported on this network")

        self.synths = self.load_synths()
        logger.info(f'loaded {len(self.synths)} synths')

    def __repr__(self):
        return "synthetix"

    @lru_cache(maxsize=None)
    def get_address(self, name):
        """
        Get contract from Synthetix registry.
        See also https://docs.synthetix.io/addresses/
        """
        address_resolver = contract(addresses[chain.id])
        address = address_resolver.getAddress(encode_single('bytes32', name.encode()))
        proxy = contract(address)
        return contract(proxy.target()) if hasattr(proxy, 'target') else proxy

    def load_synths(self):
        """
        Get target addresses of all synths.
        """
        proxy_erc20 = self.get_address('ProxyERC20')
        return fetch_multicall(
            *[
                [proxy_erc20, 'availableSynths', i]
                for i in range(proxy_erc20.availableSynthCount())
            ]
        )

    @lru_cache(maxsize=None)
    def __contains__(self, token):
        """
        Check if a token is a synth.
        """
        token = contract(token)
        if not hasattr(token, 'target'):
            return False
        target = token.target()
        if target in self.synths and contract(target).proxy() == token:
            return True
        return False

    @lru_cache(maxsize=None)
    def get_currency_key(self, token):
        target = contract(token).target()
        return contract(target).currencyKey()

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, token, block=None):
        """
        Get a price of a synth in dollars.
        """
        rates = self.get_address('ExchangeRates')
        key = self.get_currency_key(token)
        try:
            return rates.rateForCurrency(key, block_identifier=block) / 1e18
        except ValueError:
            return None


synthetix = None
try:
    synthetix = Synthetix()
except UnsupportedNetwork:
    pass
