import logging
from collections import Counter
from time import time

from brownie import chain
from collections import Counter
from joblib import Parallel, delayed

import yearn.iearn
import yearn.ironbank
import yearn.special
import yearn.v1.registry
import yearn.v2.registry
from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
from yearn.outputs.victoria import output_base, output_wallets
from yearn.prices import constants
from yearn.utils import contract

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
                "v1": yearn.v1.registry.Registry(watch_events_forever=watch_events_forever),
                "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
                "ib": yearn.ironbank.Registry(exclude_ib_tvl=exclude_ib_tvl),
                "special": yearn.special.Registry(),
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
        else:
            raise UnsupportedNetwork('yearn is not supported on this network')

        self.exclude_ib_tvl = exclude_ib_tvl

        if load_strategies:
            self.registries["v2"].load_strategies()
        if load_harvests:
            self.registries["v2"].load_harvests()
        if load_transfers:
            self.registries['v1'].load_transfers()
            self.registries['v2'].load_transfers()
        logger.info('loaded yearn in %.3fs', time() - start)


    def active_vaults_at(self, block=None):
        active = [
            vault
            for registry in self.registries.values()
            for vault in registry.active_vaults_at(block=block)
            # [yGov] Doesn't count for this context
            if vault.vault != contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")
        ]
        return active
    
    
    def describe(self, block=None):
        desc = Parallel(4, "threading")(
            delayed(self.registries[key].describe)(block=block)
            for key in self.registries
        )
        results_dict = dict(zip(self.registries, desc))
        wallet_balances = Counter()
        for registry in desc:
            for vault, data in registry.items():
                try:
                    for wallet, bals in data['wallet balances'].items():
                        wallet_balances[wallet] += bals["usd balance"]
                except: # process vaults, not aggregated stats
                    pass # TODO: add total wallets and wallet balances for earn, ib, special
        agg_stats = {
            "agg_stats": {
                "total wallets": len(wallet_balances),
                "wallet balances usd": wallet_balances
            }
        }
        results_dict.update(agg_stats)
        return results_dict


    def describe_wallets(self, block=None):
        from yearn.outputs.describers.registry import RegistryWalletDescriber
        describer = RegistryWalletDescriber()
        data = Parallel(4,'threading')(delayed(describer.describe_wallets)(registry, block=block) for registry in self.registries.items())
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


    def total_value_at(self, block=None):
        desc = Parallel(4, "threading")(
            delayed(self.registries[key].total_value_at)(block=block)
            for key in self.registries
        )
        return dict(zip(self.registries, desc))
        

    def export(self, block, ts):
        start = time()
        data = self.describe(block)
        output_base.export(block, ts, data)
        products = list(data.keys())
        if self.exclude_ib_tvl and block > constants.ib_snapshot_block:
            products.remove('ib')
        tvl = sum(vault['tvl'] for (product, product_values) in data.items() if product in products for vault in product_values.values() if type(vault) == dict)
        logger.info('exported block=%d tvl=%.0f took=%.3fs', block, tvl, time() - start)

    
    def export_wallets(self, block, ts):
        start = time()
        data = self.describe_wallets(block)
        output_wallets.export(ts,data)
        logger.info('exported block=%d took=%.3fs', block, time() - start)
