import logging
from typing import Dict, List, Optional

from brownie.convert.datatypes import EthAddress
from cachetools.func import ttl_cache
from y.constants import CHAINID
from y.networks import Network

from yearn.exceptions import MulticallError, UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.typing import Address, AddressOrContract, Block, VaultVersion
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)

# yearn lens adapter addresses
addresses = {
    Network.Mainnet: {
        'v1': '0xce29d34C8e88A2E1eDde10AD4eEE4f3e379fc041',
        'v2': '0x240315db938d44bb124ae619f5fd0269a02d1271',
        'ib': '0xFF0bd2d0C7E9424ccB149ED3757155eEf41a793D',
    },
    Network.Fantom: {
        'v2': '0xF628Fb7436fFC382e2af8E63DD7ccbaa142E3cd1',
        'ib': '0x8CafAF31Ee6374C02EedF1AD68dDb193dDAC29A2',
    },
    Network.Arbitrum: {
        'v2': '0x57AA88A0810dfe3f9b71a9b179Dd8bF5F956C46A',
        'ib': '0xf900ea42c55D165Ca5d5f50883CddD352AE48F40',
    },
    Network.Optimism: {
        'v2': '0xBcfCA75fF12E2C1bB404c2C216DBF901BE047690',
    },
    Network.Base: {
        'v2': '0xACd0CEa837A6E6f5824F4Cac6467a67dfF4B0868',
    }
}


class YearnLens(metaclass=Singleton):
    def __init__(self, force_init: bool = False) -> None:
        if CHAINID not in addresses and not force_init:
            raise UnsupportedNetwork('yearn is not supported on this network')
        self.markets

    @property
    @ttl_cache(ttl=3600)
    def markets(self) -> Dict[VaultVersion,List[EthAddress]]:
        if CHAINID not in addresses:
            return {}

        markets = {
            name: list(contract(addr).assetsAddresses())
            for name, addr in addresses[CHAINID].items()
            if name in ['v1', 'v2']
        }
        log_counts = ', '.join(f'{len(markets[name])} {name}' for name in markets)
        logger.info(f'loaded {log_counts} markets')
        return markets

    def __contains__(self, token: AddressOrContract) -> bool:
        # hard check, works with production vaults
        return any(token in market for market in self.markets.values())

    def is_yearn_vault(self, token: Address) -> bool:
        # soft check, works with any contracts using a compatible interface
        vault = contract(token)
        return any(
            all(hasattr(vault, attr) for attr in kind)
            for kind in [
                ['pricePerShare', 'token', 'decimals'],
                ['getPricePerFullShare', 'token'],
            ]
        )

    def get_price(self, token: Address, block: Optional[Block] = None) -> Optional[float]:
        # v2 vaults use pricePerShare scaled to underlying token decimals
        vault = contract(token)
        if hasattr(vault, 'pricePerShare'):
            try:
                share_price, underlying, decimals, supply = fetch_multicall(
                    [vault, 'pricePerShare'],
                    [vault, 'token'],
                    [vault, 'decimals'],
                    [vault, 'totalSupply'],
                    block=block,
                    require_success=True,
                )
            except MulticallError:
                return None
            else:
                if supply == 0:
                    return 0
                return [share_price / 10 ** decimals, underlying]

        # v1 vaults use getPricePerFullShare scaled to 18 decimals
        if hasattr(vault, 'getPricePerFullShare'):
            try:
                share_price, underlying, supply = fetch_multicall(
                    [vault, 'getPricePerFullShare'],
                    [vault, 'token'],
                    [vault, 'totalSupply'],
                    block=block,
                    require_success=True,
                )
            except MulticallError:
                return None
            else:
                if supply == 0:
                    return 0
                return [share_price / 1e18, underlying]


yearn_lens = YearnLens(force_init=True)
