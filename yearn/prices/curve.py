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
import threading
import time
from collections import defaultdict
from enum import IntEnum
from functools import lru_cache

from brownie import ZERO_ADDRESS, chain
from brownie.convert import to_address
from cachetools.func import lru_cache, ttl_cache
from yearn.events import create_filter, decode_logs
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.utils import Singleton, contract
from yearn.decorators import sentry_catch_all, wait_or_exit_after

from yearn.prices import magic

logger = logging.getLogger(__name__)

ADDRESS_PROVIDER = '0x0000000022D53366457F9d5E68Ec105046FC4383'
BASIC_TOKENS = {
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # dai
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # weth
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # eth
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # wbtc
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620",  # seur
    "0x514910771AF9Ca656af840dff83E8264EcF986CA",  # link
    "0xD533a949740bb3306d119CC777fa900bA034cd52",  # crv
    "0x95dFDC8161832e4fF7816aC4B6367CE201538253",  # ibkrw
    "0xFAFdF0C4c1CB09d430Bf88c75D88BB46DAe09967",  # ibaud
    "0x69681f8fde45345C3870BCD5eaf4A05a60E7D227",  # ibgbp
    "0x1CC481cE2BD2EC7Bf67d1Be64d4878b16078F309",  # ibchf
    "0x5555f75e3d5278082200Fb451D1b6bA946D8e13b",  # ibjpy
    "0xC581b735A1688071A1746c968e0798D642EDE491",  # eurt
    "0x99D8a9C45b2ecA8864373A26D1459e3Dff1e17F3",  # mim
    "0x853d955aCEf822Db058eb8505911ED77F175b99e",  # frax
    "0x956F47F50A910163D8BF957Cf5846D573E7f87CA",  # fei
    "0xBC6DA0FE9aD5f3b0d58160288917AA56653660E9",  # alusd
}
curve_contracts = {
    Network.Mainnet: {
        'address_provider': ADDRESS_PROVIDER,
        'crv': '0xD533a949740bb3306d119CC777fa900bA034cd52',
        'voting_escrow': '0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2',
        'gauge_controller': '0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB',
        # additional factories not listed as metapool factory
        # if we need to manually add a curve factory that isn't recorded
        # on the registry, uncomment the below line and paste it into the list
        #'factories': []
    },
    Network.Fantom: {
        'address_provider': ADDRESS_PROVIDER,
    },
    Network.Arbitrum: {
        'address_provider': ADDRESS_PROVIDER,
    },
}


class Ids(IntEnum):
    Main_Registry = 0
    PoolInfo_Getters = 1
    Exchanges = 2
    Metapool_Factory = 3
    Fee_Distributor = 4
    CryptoSwap_Registry = 5
    CryptoPool_Factory = 6


class CurveRegistry(metaclass=Singleton):

    @wait_or_exit_after
    def __init__(self):
        if chain.id not in curve_contracts:
            raise UnsupportedNetwork("curve is not supported on this network")

        addrs = curve_contracts[chain.id]
        if chain.id == Network.Mainnet:
            self.crv = contract(addrs['crv'])
            self.voting_escrow = contract(addrs['voting_escrow'])
            self.gauge_controller = contract(addrs['gauge_controller'])

        self.identifiers = defaultdict(list)  # id -> versions
        self.registries = defaultdict(set)  # registry -> pools
        self.factories = defaultdict(set)  # factory -> pools
        self.token_to_pool = dict()  # lp_token -> pool
        self.address_provider = contract(addrs['address_provider'])

        self._done = threading.Event()
        self._thread = threading.Thread(target=self.watch_events, daemon=True)
        self._has_exception = False
        self._thread.start()

    @sentry_catch_all
    def watch_events(self):
        address_provider_filter = create_filter(str(self.address_provider))
        registries = []
        registries_filter = None

        while True:
            # fetch all registries and factories from address provider
            for event in decode_logs(address_provider_filter.get_new_entries()):
                if event.name == 'NewAddressIdentifier':
                    self.identifiers[Ids(event['id'])].append(event['addr'])
                if event.name == 'AddressModified':
                    self.identifiers[Ids(event['id'])].append(event['new_address'])

            # if registries were updated, recreate the filter
            _registries = [
                self.identifiers[i][-1]
                for i in [Ids.Main_Registry, Ids.CryptoSwap_Registry]
            ]
            if _registries != registries:
                registries = _registries
                registries_filter = create_filter(registries)

            # fetch pools from the latest registries
            for event in decode_logs(registries_filter.get_new_entries()):
                if event.name == 'PoolAdded':
                    self.registries[event.address].add(event['pool'])
                    lp_token = contract(event.address).get_lp_token(event['pool'])
                    self.token_to_pool[lp_token] = event['pool']

            # load metapool and curve v5 factories
            self.load_factories()

            if not self._done.is_set():
                self._done.set()
                logger.info(f'loaded {len(self.token_to_pool)} pools from {len(self.registries)} registries and {len(self.factories)} factories')

            time.sleep(600)

    def read_pools(self, registry):
        registry = contract(registry)
        return fetch_multicall(
            *[[registry, 'pool_list', i] for i in range(registry.pool_count())]
        )

    def load_factories(self):
        # factory events are quite useless, so we use a different method
        for factory in self.identifiers[Ids.Metapool_Factory]:
            pool_list = self.read_pools(factory)
            for pool in pool_list:
                # for metpool factories pool is the same as lp token
                self.token_to_pool[pool] = pool
                self.factories[factory].add(pool)

        for factory in self.identifiers[Ids.CryptoPool_Factory]:
            pool_list = self.read_pools(factory)
            for pool in pool_list:
                if pool in self.factories[factory]:
                    continue
                # for curve v5 pools, pool and lp token are separate
                lp_token = contract(factory).get_token(pool)
                self.token_to_pool[lp_token] = pool
                self.factories[factory].add(pool)


        # we keep this so we can manually add factories that haven't yet been added to the on-chain Curve Registry
        for factory in curve_contracts[chain.id].get('factories', []):
            pool_list = self.read_pools(factory)
            for pool in pool_list:
                if pool in self.factories[factory]:
                    continue
                # for curve v5 pools, pool and lp token are separate
                lp_token = contract(factory).get_token(pool)
                self.token_to_pool[lp_token] = pool
                self.factories[factory].add(pool)

    def get_factory(self, pool):
        """
        Get metapool factory that has spawned a pool.
        """
        try:
            return next(
                factory
                for factory, factory_pools in self.factories.items()
                if str(pool) in factory_pools
            )
        except StopIteration:
            return None

    def get_registry(self, pool):
        """
        Get registry containing a pool.
        """
        try:
            return next(
                registry
                for registry, pools in self.registries.items()
                if str(pool) in pools
            )
        except StopIteration:
            return None

    def __contains__(self, token):
        return self.get_pool(token) is not None

    @lru_cache(maxsize=None)
    def get_pool(self, token):
        """
        Get Curve pool (swap) address by LP token address. Supports factory pools.
        """
        token = to_address(token)
        if token in self.token_to_pool:
            return self.token_to_pool[token]

    @lru_cache(maxsize=None)
    def get_gauge(self, pool):
        """
        Get liquidity gauge address by pool.
        """
        pool = to_address(pool)
        factory = self.get_factory(pool)
        registry = self.get_registry(pool)
        if factory and hasattr(contract(factory), 'get_gauge'):
            gauge = contract(factory).get_gauge(pool)
            if gauge != ZERO_ADDRESS:
                return gauge
        elif registry:
            gauges, types = contract(registry).get_gauges(pool)
            if gauges[0] != ZERO_ADDRESS:
                return gauges[0]

    @lru_cache(maxsize=None)
    def get_coins(self, pool):
        """
        Get coins of pool.
        """
        pool = to_address(pool)
        factory = self.get_factory(pool)
        registry = self.get_registry(pool)
        if factory:
            coins = contract(factory).get_coins(pool)
        elif registry:
            coins = contract(registry).get_coins(pool)

        # pool not in registry
        if set(coins) == {ZERO_ADDRESS}:
            coins = fetch_multicall(*[[contract(pool), 'coins', i] for i in range(8)])

        return [coin for coin in coins if coin not in {None, ZERO_ADDRESS}]

    @lru_cache(maxsize=None)
    def get_underlying_coins(self, pool):
        pool = to_address(pool)
        factory = self.get_factory(pool)
        registry = self.get_registry(pool)

        if factory:
            factory = contract(factory)
            # new factory reverts for non-meta pools
            if not hasattr(factory, 'is_meta') or factory.is_meta(pool):
                if hasattr(factory, 'get_underlying_coins'):
                    coins = factory.get_underlying_coins(pool)
                elif hasattr(factory, 'get_coins'):
                    coins = factory.get_coins(pool)
                else:
                    coins = {ZERO_ADDRESS}
            else:
                coins = factory.get_coins(pool)
        elif registry:
            coins = contract(registry).get_underlying_coins(pool)

        # pool not in registry, not checking for underlying_coins here
        if set(coins) == {ZERO_ADDRESS}:
            return self.get_coins(pool)

        return [coin for coin in coins if coin != ZERO_ADDRESS]

    @lru_cache(maxsize=None)
    def get_decimals(self, pool):
        pool = to_address(pool)
        factory = self.get_factory(pool)
        registry = self.get_registry(pool)
        source = contract(factory or registry)
        decimals = source.get_decimals(pool)

        # pool not in registry
        if not any(decimals):
            coins = self.get_coins(pool)
            decimals = fetch_multicall(
                *[[contract(token), 'decimals'] for token in coins]
            )

        return [dec for dec in decimals if dec != 0]

    def get_balances(self, pool, block=None):
        """
        Get {token: balance} of liquidity in the pool.
        """
        pool = to_address(pool)
        factory = self.get_factory(pool)
        registry = self.get_registry(pool)
        coins = self.get_coins(pool)
        decimals = self.get_decimals(pool)

        try:
            source = contract(factory or registry)
            balances = source.get_balances(pool, block_identifier=block)
        # fallback for historical queries
        except ValueError:
            balances = fetch_multicall(
                *[[contract(pool), 'balances', i] for i, _ in enumerate(coins)]
            )

        if not any(balances):
            raise ValueError(f'could not fetch balances {pool} at {block}')

        return {
            coin: balance / 10 ** dec
            for coin, balance, dec in zip(coins, balances, decimals)
        }

    def get_tvl(self, pool, block=None):
        """
        Get total value in Curve pool.
        """
        pool = to_address(pool)
        balances = self.get_balances(pool, block=block)

        return sum(
            amount * magic.get_price(coin, block=block)
            for coin, amount in balances.items()
        )

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, token, block=None):
        token = to_address(token)
        pool = self.get_pool(token)
        # crypto pools can have different tokens, use slow method
        if hasattr(contract(pool), 'price_oracle'):
            try:
                tvl = self.get_tvl(pool, block=block)
            except ValueError:
                return None
            supply = contract(token).totalSupply(block_identifier=block) / 1e18
            if supply == 0:
                return 0
            return tvl / supply

        # approximate by using the most common base token we find
        coins = self.get_underlying_coins(pool)
        try:
            coin = (set(coins) & BASIC_TOKENS).pop()
        except KeyError:
            coin = coins[0]

        virtual_price = contract(pool).get_virtual_price(block_identifier=block) / 1e18
        return virtual_price * magic.get_price(coin, block)

    def calculate_boost(self, gauge, addr, block=None):
        results = fetch_multicall(
            [gauge, "balanceOf", addr],
            [gauge, "totalSupply"],
            [gauge, "working_balances", addr],
            [gauge, "working_supply"],
            [self.voting_escrow, "balanceOf", addr],
            [self.voting_escrow, "totalSupply"],
            block=block,
        )
        results = [x / 1e18 for x in results]
        (
            gauge_balance,
            gauge_total,
            working_balance,
            working_supply,
            vecrv_balance,
            vecrv_total,
        ) = results
        try:
            boost = working_balance / gauge_balance * 2.5
        except ZeroDivisionError:
            boost = 1

        min_vecrv = vecrv_total * gauge_balance / gauge_total
        lim = gauge_balance * 0.4 + gauge_total * min_vecrv / vecrv_total * 0.6
        lim = min(gauge_balance, lim)

        _working_supply = working_supply + lim - working_balance
        noboost_lim = gauge_balance * 0.4
        noboost_supply = working_supply + noboost_lim - working_balance
        try:
            max_boost_possible = (lim / _working_supply) / (
                noboost_lim / noboost_supply
            )
        except ZeroDivisionError:
            max_boost_possible = 1

        return {
            "gauge balance": gauge_balance,
            "gauge total": gauge_total,
            "vecrv balance": vecrv_balance,
            "vecrv total": vecrv_total,
            "working balance": working_balance,
            "working total": working_supply,
            "boost": boost,
            "max boost": max_boost_possible,
            "min vecrv": min_vecrv,
        }

    def calculate_apy(self, gauge, lp_token, block=None):
        crv_price = magic.get_price(self.crv)
        pool = contract(self.get_pool(lp_token))
        results = fetch_multicall(
            [gauge, "working_supply"],
            [self.gauge_controller, "gauge_relative_weight", gauge],
            [gauge, "inflation_rate"],
            [pool, "get_virtual_price"],
            block=block,
        )
        results = [x / 1e18 for x in results]
        working_supply, relative_weight, inflation_rate, virtual_price = results
        token_price = magic.get_price(lp_token, block=block)
        try:
            rate = (
                inflation_rate * relative_weight * 86400 * 365 / working_supply * 0.4
            ) / token_price
        except ZeroDivisionError:
            rate = 0

        return {
            "crv price": crv_price,
            "relative weight": relative_weight,
            "inflation rate": inflation_rate,
            "virtual price": virtual_price,
            "crv reward rate": rate,
            "crv apy": rate * crv_price,
            "token price": token_price,
        }


curve = None
try:
    curve = CurveRegistry()
except UnsupportedNetwork:
    pass
