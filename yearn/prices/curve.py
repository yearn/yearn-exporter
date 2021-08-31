from yearn.events import create_filter, decode_logs
from brownie import ZERO_ADDRESS, Contract, multicall
from cachetools.func import ttl_cache
from toolz import take, concat
from functools import cached_property, lru_cache
from collections import defaultdict
from yearn.utils import Singleton, contract
from yearn.cache import memory
from yearn.multicall2 import fetch_multicall
import logging

"""
Registry versions:
id 0 (Main Registry)
    v1 = 0x7D86446dDb609eD0F5f8684AcF30380a356b2B4c
    v2 = 0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5
id 2 (Exchanges)
    v1 = 0xD1602F68CC7C4c7B59D686243EA35a9C73B0c6a2
    v2 = 0x2393c368C70B42f055a4932a3fbeC2AC9C548011
id 3 (Metapool Factory)
    v1 = 0x0959158b6040D32d04c301A72CBFD6b39E21c9AE
    v2 = 0xB9fC157394Af804a3578134A6585C0dc9cc990d4
"""

logger = logging.getLogger(__name__)


class NonCurvePool(ValueError):
    pass


# https://curve.readthedocs.io/registry-address-provider.html
class CurveRegistry(metaclass=Singleton):
    def __init__(self):
        self.pools = set()
        self.identifiers = defaultdict(list)
        self.addres_provider = contract('0x0000000022D53366457F9d5E68Ec105046FC4383')

        self.watch_events()

    def watch_events(self):
        # fetch all registries and factories from address provider
        log_filter = create_filter(str(self.addres_provider))
        for event in decode_logs(log_filter.get_new_entries()):
            if event.name == 'NewAddressIdentifier':
                self.identifiers[event['id']].append(event['addr'])
            if event.name == 'AddressModified':
                self.identifiers[event['id']].append(event['new_address'])

        logger.info(f'{self.identifiers}')

        # fetch pools from the latest registry
        log_filter = create_filter(str(self.latest_registry))
        for event in decode_logs(log_filter.get_new_entries()):
            if event.name == 'PoolAdded':
                self.pools.add(event['pool'])

        logger.info(f'{len(self.pools)} pools, {self.pools}')

    @property
    def latest_registry(self):
        return contract(self.identifiers[0][-1])

    @property
    def metapool_factories(self):
        return [contract(factory) for factory in self.identifiers[3]]

    @property
    @ttl_cache(ttl=3600)
    def metapools_by_factory(self):
        with multicall:
            data = {
                str(factory): [
                    factory.pool_list(i) for i in range(factory.pool_count())
                ]
                for factory in self.metapool_factories
            }
        return data

    def is_factory_pool(self, pool):
        return str(pool) in concat(self.metapools_by_factory.values())

    @lru_cache(maxsize=None)
    def _pool_from_lp_token(self, token):
        return self.latest_registry.get_pool_from_lp_token(token)

    def get_pool(self, token):
        if self.is_factory_pool(token):
            return token

        pool = self._pool_from_lp_token(token)
        if pool == ZERO_ADDRESS:
            raise NonCurvePool(token)

        return pool


# fold underlying tokens into one of the basic tokens
BASIC_TOKENS = {
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # dai
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # weth
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # eth
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # wbtc
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620",  # seur
    "0x514910771AF9Ca656af840dff83E8264EcF986CA",  # link
}


@memory.cache()
def get_coins_from_pool(pool_address):
    pool = Contract(pool_address)
    try:
        all_coins = fetch_multicall(*[[pool, 'coins', i] for i in range(8)])
        coins = [
            coin for coin in all_coins if coin != ZERO_ADDRESS and coin is not None
        ]
        return coins
    except AttributeError:
        return []


@memory.cache()
def is_curve_lp_token(token):
    try:
        return get_pool(token) != ZERO_ADDRESS
    except ValueError as error:
        return False


@memory.cache()
def is_curve_lp_crypto_pool(token):
    pool = Contract(get_pool(token))
    if hasattr(pool, "price_oracle"):
        return True
    else:
        return False


@memory.cache()
def get_underlying_coins(token):
    pool = get_pool(token)
    coins = curve_registry.get_underlying_coins(pool)
    if set(coins) == {ZERO_ADDRESS}:
        coins = get_coins_from_pool(pool)
    return [coin for coin in coins if coin != ZERO_ADDRESS]


def cryptopool_lp_price(token, block=None):
    pool = Contract(get_pool(token))
    token = Contract(token)
    result = get_coins_from_pool(pool.address)
    tokens = [Contract(token) for token in result if token]
    n = len(tokens)
    result = iter(
        fetch_multicall(
            [token, 'totalSupply'],
            *[[token, 'decimals'] for token in tokens],
            *[[pool, 'balances', i] for i in range(n)],
            *[[pool, 'price_oracle', i] for i in range(n - 1)],
            block=block,
        )
    )
    supply = next(result) / 1e18
    scales = [10 ** decimals for decimals in take(n, result)]
    balances = [balance / scale for balance, scale in zip(take(n, result), scales)]
    # oracles return price with the first coin as a quote currency
    prices = [1] + [price / 1e18 for price in take(n - 1, result)]
    scale = sum(balance * price for balance, price in zip(balances, prices)) / supply
    return [scale, str(tokens[0])]


@ttl_cache(ttl=600)
def get_price(token, block=None):
    if is_curve_lp_crypto_pool(token):
        return cryptopool_lp_price(token, block)

    coins = get_underlying_coins(token)
    try:
        coin = (set(coins) & BASIC_TOKENS).pop()
    except KeyError:
        coin = coins[0]

    # there is a registry.get_virtual_price_from_lp_token,
    # but we call pool in case the registry was not deployed at the block
    pool = Contract(get_pool(token))
    virtual_price = pool.get_virtual_price(block_identifier=block) / 1e18
    return [virtual_price, coin]


curve = CurveRegistry()
