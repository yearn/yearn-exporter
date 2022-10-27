import asyncio
import logging
from collections import Counter
from time import time
from typing import List

from brownie import chain

import yearn.iearn
import yearn.ironbank
import yearn.special
import yearn.v1.registry
import yearn.v2.registry
from yearn.exceptions import UnsupportedNetwork
from yearn.ironbank import addresses as ironbank_registries
from yearn.networks import Network
from yearn.outputs.victoria.output_helper import (_flatten_dict,
                                                  _get_label_values, mapping)
from yearn.outputs.victoria.victoria import _build_item
from yearn.prices import constants
from yearn.utils import contract_creation_block

logger = logging.getLogger(__name__)


class Yearn:
    """
    Can describe all products.
    """

    def __init__(self, load_strategies=True, load_harvests=False, load_transfers=False, watch_events_forever=True, exclude_ib_tvl=True) -> None:
        start = time()
        if chain.id == Network.Mainnet:
            self.registries = {
                "earn": yearn.iearn.Registry(),
                "v1": yearn.v1.registry.Registry(),
                "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
                "ib": yearn.ironbank.Registry(exclude_ib_tvl=exclude_ib_tvl),
                "special": yearn.special.Registry(),
            }
        elif chain.id ==  Network.Gnosis:
            self.registries = {
                "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
            }
        elif chain.id ==  Network.Fantom:
            self.registries = {
                "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
                "ib": yearn.ironbank.Registry(exclude_ib_tvl=exclude_ib_tvl),
            }
        elif chain.id == Network.Arbitrum:
            self.registries = {
                "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
                "ib": yearn.ironbank.Registry(exclude_ib_tvl=exclude_ib_tvl),
            }
        elif chain.id == Network.Optimism:
            self.registries = {
                "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
                "ib": yearn.ironbank.Registry(exclude_ib_tvl=exclude_ib_tvl),
            }
        else:
            raise UnsupportedNetwork('yearn is not supported on this network')

        self.exclude_ib_tvl = exclude_ib_tvl

        if load_strategies:
            self.registries["v2"].load_strategies()
        if load_harvests:
            self.registries["v2"].load_harvests()
        logger.info('loaded yearn in %.3fs', time() - start)


    def active_vaults_at(self, block=None):
        active = [
            vault
            for registry in self.registries.values()
            for vault in registry.active_vaults_at(block=block)
        ]
        
        # [yGov] Doesn't count for this context
        if chain.id == Network.Mainnet and (
            block is None
            or block > contract_creation_block(yearn.special.Ygov().vault.address)
            ): active.remove(yearn.special.Ygov())

        return active
    
    
    async def describe(self, block=None):
        if block is None:
            block = chain.height
        desc = await asyncio.gather(*[self.registries[key].describe(block=block) for key in self.registries])
        return dict(zip(self.registries, desc))


    async def describe_wallets(self, block=None):
        from yearn.outputs.describers.registry import RegistryWalletDescriber
        describer = RegistryWalletDescriber()
        data = await asyncio.gather(*[describer.describe_wallets(registry, block=block) for registry in self.registries.items()])
        data = {registry:desc for registry,desc in zip(self.registries,data)}

        wallet_balances = Counter()
        for registry, reg_desc in data.items():
            for wallet, usd_bal in reg_desc['wallet balances usd'].items():
                wallet_balances[wallet] += usd_bal
        
        agg_stats = {
            "agg_stats": {
                "total wallets": len(wallet_balances),
                "active wallets": sum(1 if balance > 50 else 0 for wallet, balance in wallet_balances.items()),
                "wallets > $5k": sum(1 if balance > 5000 else 0 for wallet, balance in wallet_balances.items()),
                "wallets > $50k": sum(1 if balance > 50000 else 0 for wallet, balance in wallet_balances.items()),
                "wallet balances usd": wallet_balances
            }
        }
        data.update(agg_stats)
        return data


    async def total_value_at(self, block=None):
        desc = await asyncio.gather(*[self.registries[key].total_value_at(block=block) for key in self.registries])
        return dict(zip(self.registries, desc))
        

    async def data_for_export(self, block, timestamp) -> List:
        start = time()
        data = await self.describe(block)
        products = list(data.keys())
        if 'ib' in products and self.exclude_ib_tvl and block > constants.ib_snapshot_block:
            products.remove('ib')
        tvl = sum(
            vault['tvl']
            for (product, product_values) in data.items()
            if product in products
            for vault in product_values.values() if type(vault) == dict
        )
        if tvl == 0:
            print(data)
        logger.info('exported block=%d tvl=%.0f took=%.3fs', block, tvl, time() - start)

        metrics_to_export = []

        if chain.id == Network.Mainnet:
            simple_products = ["v1", "earn", "ib", "special"]
        elif chain.id in ironbank_registries:
            simple_products = ["ib"]
        else:
            simple_products = []

        for product in simple_products:
            metric = mapping[product]["metric"]
            for vault, params in data[product].items():

                for key, value in params.items():
                    if key in ["address", "version", "experimental"] or value is None:
                        continue

                    has_experiments = product == "special"

                    label_values = _get_label_values(params, [vault, key], has_experiments)
                    label_names = mapping[product]["labels"]

                    if product == "ib" and key == 'tvl' and block >= constants.ib_snapshot_block:
                        # create one item with tvl=0 that will be used in existing dashboards
                        item_legacy = _build_item(metric, label_names, label_values, 0, timestamp)
                        metrics_to_export.append(item_legacy)
                        # create a second item to track ib tvl separately
                        item_own = _build_item(f'{metric}_own', label_names, label_values, value, timestamp)
                        metrics_to_export.append(item_own)
                    else:
                        item = _build_item(metric, label_names, label_values, value, timestamp)
                        metrics_to_export.append(item)

        for vault, params in data["v2"].items():
            metric = mapping["v2"]["metric"]
            for key, value in params.items():
                if key in ["address", "version", "experimental", "strategies"] or value is None:
                    continue

                label_values = _get_label_values(params, [vault, key], True)
                label_names = mapping["v2"]["labels"]

                item = _build_item(metric, label_names, label_values, value, timestamp)
                metrics_to_export.append(item)

            # strategies can have nested structs
            metric = mapping["v2_strategy"]["metric"]
            for strategy, strategy_params in data["v2"][vault]["strategies"].items():
                flat = _flatten_dict(strategy_params)
                for key, value in flat.items():
                    if key in ["address", "version", "experimental"] or value is None:
                        continue

                    label_values = _get_label_values(params, [vault, strategy, key], True)
                    label_names = mapping["v2_strategy"]["labels"]

                    item = _build_item(metric, label_names, label_values, value or 0, timestamp)
                    metrics_to_export.append(item)

            return metrics_to_export

    
    async def wallet_data_for_export(self, block: int, timestamp: int):
        data = await self.describe_wallets(block)
        metrics_to_export = []
        for key, value in data['agg_stats'].items():
            if key == 'wallet balances usd':
                for wallet, usd_bal in value.items():
                    label_names = ["param","wallet"]
                    label_values = ["balance usd",wallet]
                    item = _build_item("aggregate", label_names, label_values, usd_bal, timestamp)
                    metrics_to_export.append(item)
                continue
            label_names = ['param']
            label_values = [key]
            item = _build_item("aggregate", label_names, label_values, value, timestamp)
            metrics_to_export.append(item)
        for key in data.keys():
            if key == 'agg_stats':
                continue
            product = key
            metric = mapping[product]["metric"]
            for key, value in data[product].items():
                if key in mapping[product]["agg_stats"]:
                    label_names = ['param']
                    label_values = [key]
                    item = _build_item(metric, label_names, label_values, value, timestamp)
                    metrics_to_export.append(item)
                    continue
                elif key == "wallet balances usd":
                    for wallet, usd_bal in value.items():
                        label_names = ["param","wallet"]
                        label_values = ["balance usd",wallet]
                        item = _build_item(metric, label_names, label_values, usd_bal, timestamp)
                        metrics_to_export.append(item)
                    continue
                
                vault, params = key, value
                for k, v in params.items():
                    if k == 'wallet balances':
                        for wallet, bals in v.items():
                            for denom, bal in bals.items():
                                label_values = [wallet] + _get_label_values(params, [vault, denom], product in ['v2','special'])
                                label_names = ["wallet"] + mapping[product]["labels"]
                                item = _build_item(metric, label_names, label_values, bal, timestamp)
                                metrics_to_export.append(item)
                        continue

                    label_values = _get_label_values(params, [vault, k], True)
                    label_names = mapping[product]["labels"]

                    item = _build_item(metric, label_names, label_values, v, timestamp)
                    metrics_to_export.append(item)
