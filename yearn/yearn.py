import logging
from time import time

from collections import Counter
from joblib import Parallel, delayed

import yearn.iearn
import yearn.ironbank
import yearn.special
import yearn.v2.registry
import yearn.v1.registry
from yearn.outputs import victoria


logger = logging.getLogger(__name__)


class Yearn:
    """
    Can describe all products.
    """

    def __init__(self, load_strategies=True, load_harvests=False, load_transfers=False, watch_events_forever=True) -> None:
        start = time()
        self.registries = {
            "earn": yearn.iearn.Registry(),
            "v1": yearn.v1.registry.Registry(watch_events_forever=watch_events_forever),
            "v2": yearn.v2.registry.Registry(watch_events_forever=watch_events_forever),
            "ib": yearn.ironbank.Registry(),
            "special": yearn.special.Registry(),
        }
        if load_strategies:
            self.registries["v2"].load_strategies()
        if load_harvests:
            self.registries["v2"].load_harvests()
        if load_transfers:
            self.registries['v1'].load_transfers()
            self.registries['v2'].load_transfers()
        logger.info('loaded yearn in %.3fs', time() - start)

    def describe(self, block=None):
        desc = Parallel(4, "threading")(
            delayed(self.registries[key].describe)(block=block)
            for key in self.registries
        )
        results_dict = dict(zip(self.registries, desc))
        user_balances = Counter()
        for registry in desc:
            for vault, data in registry.items():
                try:
                    for user, bals in data['user balances'].items():
                        user_balances[user] += bals["usd balance"]
                except: # process vaults, not aggregated stats
                    pass # TODO: add total users and user balances for earn, ib, special
        print(len(user_balances))
        agg_stats = {
            "agg_stats": {
                "total users": len(user_balances),
                "user balances usd": user_balances
            }
        }
        results_dict.update(agg_stats)
        return results_dict

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
        tvl = sum(vault['tvl'] for product in data.values() for vault in product.values())
        logger.info('exported block=%d tvl=%.0f took=%.3fs', block, tvl, time() - start)
