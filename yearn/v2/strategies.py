from brownie import Contract
from yearn.utils import safe_views
from yearn.mutlicall import fetch_multicall


STRATEGY_VIEWS_SCALED = [
    "maxDebtPerHarvest",
    "minDebtPerHarvest",
    "totalDebt",
    "totalGain",
    "totalLoss",
    "estimatedTotalAssets",
    "lentTotalAssets",
    "balanceOfPool",
    "balanceOfWant",
]


class Strategy:
    def __init__(self, strategy, vault):
        self.strategy = Contract(strategy)
        self.vault = vault
        self.name = self.strategy.name()
        self._views = safe_views(self.strategy.abi)

    def __repr__(self) -> str:
        return f"<Strategy {self.strategy} name={self.name}>"

    def __eq__(self, other):
        if isinstance(other, Strategy):
            return self.strategy == other.strategy

        if isinstance(other, str):
            return self.strategy == other

        raise ValueError("Strategy is only comparable with [Strategy, str]")

    def describe(self):
        results = fetch_multicall(
            *[[self.strategy, view] for view in self._views],
            [self.vault.vault, "strategies", self.strategy],
        )
        info = dict(zip(self._views, results))
        info.update(results[-1].dict())
        for view in STRATEGY_VIEWS_SCALED:
            if view in info:
                info[view] /= self.vault.scale
        return info
