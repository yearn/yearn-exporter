"""
Curve Registry adapter. Supports regular pools, factory pools and crypto pools.
See also https://curve.readthedocs.io/registry-address-provider.html

Main Registry (id 0)
    v1 = 0x7D86446dDb609eD0F5f8684AcF30380a356b2B4c
    v2 = 0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5
Exchanges (id 2)
    v1 = 0xD1602F68CC7C4c7B59D686243EA35a9C73B0c6a2
    v2 = 0x2393c368C70B42f055a4932a3fbeC2AC9C548011
Metapool Factory (id 3)
    v1 = 0x0959158b6040D32d04c301A72CBFD6b39E21c9AE
    v2 = 0xB9fC157394Af804a3578134A6585C0dc9cc990d4
"""
import logging
from collections import defaultdict
from functools import lru_cache
from itertools import islice

from brownie import ZERO_ADDRESS
from cachetools.func import ttl_cache

from yearn.events import create_filter, decode_logs
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)

WBTC = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
BASIC_TOKENS = {
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # dai
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # weth
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # eth
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # wbtc
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620",  # seur
    "0x514910771AF9Ca656af840dff83E8264EcF986CA",  # link
}


class CurveRegistry(metaclass=Singleton):
    def __init__(self):
        self.pools = set()
        self.identifiers = defaultdict(list)
        self.addres_provider = contract('0x0000000022D53366457F9d5E68Ec105046FC4383')
        self.watch_events()

    def watch_events(self):
        # TODO keep fresh in background

        # fetch all registries and factories from address provider
        log_filter = create_filter(str(self.addres_provider))
        for event in decode_logs(log_filter.get_new_entries()):
            if event.name == 'NewAddressIdentifier':
                self.identifiers[event['id']].append(event['addr'])
            if event.name == 'AddressModified':
                self.identifiers[event['id']].append(event['new_address'])

        # fetch pools from the latest registry
        log_filter = create_filter(str(self.registry))
        for event in decode_logs(log_filter.get_new_entries()):
            if event.name == 'PoolAdded':
                self.pools.add(event['pool'])

        logger.info(f'loaded {len(self.pools)} pools')

    @property
    def registry(self):
        return contract(self.identifiers[0][-1])

    @property
    @ttl_cache(ttl=3600)
    def metapools_by_factory(self):
        """
        Read cached pools spawned by each factory.
        TODO Update on factory events
        """
        metapool_factories = [contract(factory) for factory in self.identifiers[3]]
        pool_counts = fetch_multicall(
            *[[factory, 'pool_count'] for factory in metapool_factories]
        )
        pool_lists = iter(
            fetch_multicall(
                *[
                    [factory, 'pool_list', i]
                    for factory, pool_count in zip(metapool_factories, pool_counts)
                    for i in range(pool_count)
                ]
            )
        )
        return {
            str(factory): list(islice(pool_lists, pool_count))
            for factory, pool_count in zip(metapool_factories, pool_counts)
        }

    def get_factory(self, pool):
        """
        Get metapool factory that has spawned a pool.
        """
        try:
            return next(
                factory
                for factory, factory_pools in self.metapools_by_factory.items()
                if str(pool) in factory_pools
            )
        except StopIteration:
            return None

    @lru_cache(maxsize=None)
    def _pool_from_lp_token(self, token):
        return self.registry.get_pool_from_lp_token(token)

    def get_pool(self, token):
        """
        Get Curve pool (swap) address by LP token address. Supports factory pools.
        """
        if self.get_factory(token):
            return token

        pool = self._pool_from_lp_token(token)

        if pool != ZERO_ADDRESS:
            return pool

    def get_gauge(self, pool):
        """
        Get liquidity gauge address by pool.
        """
        factory = self.get_factory(pool)
        if factory and hasattr(contract(factory), 'get_gauge'):
            gauge = contract(factory).get_gauge(pool)
            if gauge != ZERO_ADDRESS:
                return gauge

        gauges, types = self.registry.get_gauges(pool)
        if gauges[0] != ZERO_ADDRESS:
            return gauges[0]

    def get_coins(self, pool):
        """
        Get coins of pool.
        """
        factory = self.get_factory(pool)
        if factory:
            coins = contract(factory).get_coins(pool)
        else:
            coins = self.registry.get_coins(pool)

        return [coin for coin in coins if coin != ZERO_ADDRESS]

    def get_balances(self, pool, block=None):
        """
        Get {token: balance} of liquidity in the pool.
        """
        factory = self.get_factory(pool)
        source = contract(factory) if factory else self.registry
        coins, decimals = fetch_multicall(
            [source, 'get_coins', pool], [source, 'get_decimals', pool]
        )
        num_coins = len([coin for coin in coins if coin != ZERO_ADDRESS])

        try:
            balances = source.get_balances(pool, block_identifier=block)
        # fallback for historical queries
        except ValueError:
            balances = fetch_multicall(
                *[[contract(pool), 'balances', i] for i in range(num_coins)]
            )

        if not any(balances):
            return None

        return {
            coin: balance / 10 ** dec
            for coin, balance, dec in zip(coins, balances, decimals)
            if coin != ZERO_ADDRESS
        }

    def get_tvl(self, pool, block=None):
        """
        Get total value in Curve pool.
        """
        balances = self.get_balances(pool, block=block)
        if balances is None:
            return None

        return sum(
            balances[coin] * magic.get_price(coin, block=block) for coin in balances
        )

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, token, block=None):
        pool = self.get_pool(token)

        # crypto pools can have different tokens, use slow method
        if hasattr(contract(pool), 'price_oracle'):
            tvl = self.get_tvl(pool, block=block)
            if tvl is None:
                return None
            supply = contract(token).totalSupply(block_identifier=block) / 1e18
            return tvl / supply

        # approximate by using the most common base token we find
        coins = self.get_underlying_coins(pool)
        try:
            coin = (set(coins) & BASIC_TOKENS).pop()
        except KeyError:
            coin = coins[0]
            return None

        virtual_price = contract(pool).get_virtual_price(block_identifier=block) / 1e18
        return virtual_price * magic.get_price(coin, block)

    def get_underlying_coins(self, pool):
        factory = self.get_factory(pool)
        if factory:
            coins = contract(factory).get_underlying_coins(pool)
        else:
            coins = self.registry.get_underlying_coins(pool)

        return [coin for coin in coins if coin != ZERO_ADDRESS]


curve = CurveRegistry()
