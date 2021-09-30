import logging
from time import time

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

    def __init__(self, load_strategies=True, load_harvests=False) -> None:
        start = time()
        self.registries = {
            "earn": yearn.iearn.Registry(),
            "v1": yearn.v1.registry.Registry(),
            "v2": yearn.v2.registry.Registry(),
            "ib": yearn.ironbank.Registry(),
            "special": yearn.special.Registry(),
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
