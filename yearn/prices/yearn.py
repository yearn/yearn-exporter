from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.utils import Singleton, contract
from brownie import chain
from yearn.exceptions import UnsupportedNetwork
import logging
from cachetools.func import ttl_cache

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
}


class YearnLens(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('yearn is not supported on this network')
        self.markets

    @property
    @ttl_cache(ttl=3600)
    def markets(self):
        markets = {
            name: list(contract(addr).assetsAddresses())
            for name, addr in addresses[chain.id].items()
            if name in ['v1', 'v2']
        }
        log_counts = ', '.join(f'{len(markets[name])} {name}' for name in markets)
        logger.info(f'loaded {log_counts} markets')
        return markets

    def __contains__(self, token):
        # hard check, works with production vaults
        return any(token in market for market in self.markets.values())

    def is_yearn_vault(self, token):
        # soft check, works with any contracts using a compatible interface
        vault = contract(token)
        return any(
            all(hasattr(vault, attr) for attr in kind)
            for kind in [
                ['pricePerShare', 'token', 'decimals'],
                ['getPricePerFullShare', 'token'],
            ]
        )

    def get_price(self, token, block=None):
        # v1 vaults use getPricePerFullShare scaled to 18 decimals
        # v2 vaults use pricePerShare scaled to underlying token decimals
        vault = contract(token)
        if hasattr(vault, 'pricePerShare'):
            share_price, underlying, decimals = fetch_multicall(
                [vault, 'pricePerShare'],
                [vault, 'token'],
                [vault, 'decimals'],
                block=block,
            )
            if share_price and underlying and decimals:
                return [share_price / 10 ** decimals, underlying]
        if hasattr(vault, 'getPricePerFullShare'):
            share_price, underlying = fetch_multicall(
                [vault, 'getPricePerFullShare'], [vault, 'token'], block=block
            )
            if share_price and underlying:
                return [share_price / 1e18, underlying]


yearn_lens = None
try:
    yearn_lens = YearnLens()
except UnsupportedNetwork:
    pass
