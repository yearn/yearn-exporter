from dataclasses import dataclass

from brownie import interface


class Strategy:
    def __init__(self, strategy, strategy_interface):
        self.strategy = strategy_interface(strategy)
        self.vault = interface.Vault(self.strategy.vault())

    @property
    def name(self):
        # interface name
        return self.strategy._name

    def describe_base(self):
        scale = 10 ** self.vault.decimals()
        params = self.vault.strategies(self.strategy).dict()
        # scaled params
        for param in ["debtLimit", "rateLimit", "totalDebt", "totalGain", "totalLoss"]:
            params[param] /= scale
        info = {
            "debtOutstanding": self.vault.debtOutstanding(self.strategy) / scale,
            "creditAvailable": self.vault.creditAvailable(self.strategy) / scale,
            "expectedReturn": self.vault.expectedReturn(self.strategy) / scale,
            "estimatedTotalAssets": self.strategy.estimatedTotalAssets() / scale,
            "emergencyExit": self.strategy.emergencyExit(),
        }
        info.update(params)
        return info

    def describe_strategy(self):
        # override with strategy-specific params you want to track
        return {}

    def describe(self):
        try:
            info = self.describe_base()
            info.update(self.describe_strategy())
        except (ValueError, AttributeError) as e:
            print(f"error in {self.name}: {e}")
            info = {}
        return info
