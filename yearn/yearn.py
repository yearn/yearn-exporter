import logging
from collections import Counter
from time import time

from brownie import chain
from joblib import Parallel, delayed

import yearn.iearn
import yearn.ironbank
import yearn.special
import yearn.v1.registry
import yearn.v2.registry
from yearn.networks import Network
from yearn.outputs import victoria

logger = logging.getLogger(__name__)
logging.getLogger('yearn.v2.registry').setLevel(logging.DEBUG)
logging.getLogger('yearn.prices.magic').setLevel(logging.DEBUG)


class Yearn:
    """
    Can describe all products.
    """

    def __init__(self, load_strategies=True, load_harvests=False, watch_events_forever=True) -> None:
        start = time()
        match chain.id:
            case Network.Mainnet:
                self.registries = {
                    "earn": yearn.iearn.Registry(),
                    "v1": yearn.v1.registry.Registry(),
                    "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
                    "ib": yearn.ironbank.Registry(),
                    "special": yearn.special.Registry(),
                }
            case Network.Fantom:
                self.registries = {
                    "v2": yearn.v2.registry.Registry(),
                    "ib": yearn.ironbank.Registry(),
                }
            case Network.Arbitrum:
                self.registries = {
                    "v2": yearn.v2.registry.Registry(),
                    "ib": yearn.ironbank.Registry(),
                }
        if load_strategies:
            self.registries["v2"].load_strategies()
        if load_harvests:
            self.registries["v2"].load_harvests()
        logger.info('loaded yearn in %.3fs', time() - start)

    def describe(self, block=None):
        desc = Parallel(4, "threading")(
            delayed(self.registries[key].describe)(block=block)
            for key in self.registries
        )
        return dict(zip(self.registries, desc))

    def describe_wallets(self, block=None):
        registries = ['v1','v2'] # TODO: add other registries [earn, ib, special]
        data = Parallel(4,'threading')(delayed(self.registries[key].describe_wallets)(block=block) for key in registries)
        data = {registry:desc for registry,desc in zip(registries,data)}

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
        victoria.export(ts, data)
        tvl = sum(vault['tvl'] for product in data.values() for vault in product.values() if type(vault) == dict)
        logger.info('exported block=%d tvl=%.0f took=%.3fs', block, tvl, time() - start)

    
    def export_wallets(self, block, ts):
        start = time()
        data = self.describe_wallets(block)
        victoria.export_wallets(ts,data)
        logger.info('exported block=%d took=%.3fs', block, time() - start)
