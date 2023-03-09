import logging
from typing import List, Optional

from brownie import chain
from brownie.convert.datatypes import EthAddress, HexString
from cachetools.func import lru_cache, ttl_cache
from eth_abi import encode_single

from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)

addresses = {
    Network.Mainnet: '0x823bE81bbF96BEc0e25CA13170F5AaCb5B79ba83',
    Network.Optimism: '0x95A6a3f44a70172E7d50a9e28c85Dfd712756B8C',
}


class Synthetix(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in addresses:
            raise UnsupportedNetwork("synthetix is not supported on this network")

        self.synths = self.load_synths()
        logger.info(f'loaded {len(self.synths)} synths')

    @lru_cache(maxsize=128)
    def get_address(self, name: str, block: Block = None) -> EthAddress:
        """
        Get contract from Synthetix registry.
        See also https://docs.synthetix.io/addresses/
        """
        address_resolver = contract(addresses[chain.id])
        address = address_resolver.getAddress(encode_single('bytes32', name.encode()), block_identifier=block)
        proxy = contract(address)
        return contract(proxy.target()) if hasattr(proxy, 'target') else proxy

    def load_synths(self) -> List[EthAddress]:
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
    def __contains__(self, token: AddressOrContract) -> bool:
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
    def get_currency_key(self, token: Address) -> HexString:
        target = contract(token).target()
        return contract(target).currencyKey()

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, token: Address, block: Optional[Block] = None) -> Optional[float]:
        """
        Get a price of a synth in dollars.
        """
        key = self.get_currency_key(token)
        try:
            rates = self.get_address('ExchangeRates', block=block)
            return rates.rateForCurrency(key, block_identifier=block) / 1e18
        except ValueError:
            return None


synthetix = None
try:
    synthetix = Synthetix()
except UnsupportedNetwork:
    pass
