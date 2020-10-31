from dataclasses import dataclass
from brownie import interface
from brownie.network.contract import InterfaceContainer


@dataclass
class BaseStrategy:
    strategy: InterfaceContainer
    vault: InterfaceContainer = None

    def __post_init__(self):
        self.vault = interface.Vault(self.strategy.vault())

    def describe(self):
        scale = 10 ** self.vault.decimals()
        params = self.vault.strategies(self.strategy)
        return {
            "debtOutstanding": self.vault.debtOutstanding(self.strategy) / scale,
            "creditAvailable": self.vault.creditAvailable(self.strategy) / scale,
            "expectedReturn": self.vault.expectedReturn(self.strategy) / scale,
            "emergencyExit": self.strategy.emergencyExit(),
            "estimatedTotalAssets": self.strategy.estimatedTotalAssets() / scale,
            "expectedReturn": self.strategy.expectedReturn() / scale,
            "outstanding": self.strategy.outstanding() / scale,
            "reserve": self.strategy.reserve() / scale,
            "performanceFee": params[0],
            "activation": params[1],
            "debtLimit": params[2] / scale,
            "rateLimit": params[3] / scale,
            "lastReport": params[4],
            "totalDebt": params[5] / scale,
            "totalReturns": params[6] / scale,
        }
