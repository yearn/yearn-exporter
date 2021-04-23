import logging
from time import time

from joblib import Parallel, delayed

import yearn.iearn
import yearn.ironbank
import yearn.special
import yearn.v2.registry
import yearn.vaults_v1

logger = logging.getLogger(__name__)

class Yearn:
    """
    Can describe all products.
    """

    def __init__(self, load_strategies=True) -> None:
        start = time()
        self.registries = {
            "earn": yearn.iearn.Registry(),
            "v1": yearn.vaults_v1.Registry(),
            "v2": yearn.v2.registry.Registry(),
            "ib": yearn.ironbank.Registry(),
            "special": yearn.special.Registry(),
        }
        if load_strategies:
            self.registries["v2"].load_strategies()
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
