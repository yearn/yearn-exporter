from itertools import product
import yearn.v2.registry
import yearn.iearn
import yearn.ironbank
import yearn.vaults_v1
import yearn.special
from joblib import Parallel, delayed


class Yearn:
    """
    Can describe all products.
    """

    def __init__(self) -> None:
        self.registries = {
            "earn": yearn.iearn.Registry(),
            "v1": yearn.vaults_v1.Registry(),
            "v2": yearn.v2.registry.Registry(),
            "ib": yearn.ironbank.Registry(),
            "special": yearn.special.Registry(),
        }
        self.registries["v2"].load_strategies()

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
