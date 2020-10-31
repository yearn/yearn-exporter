from abc import abstractmethod
from dataclasses import dataclass
from brownie import interface
from brownie.network.contract import InterfaceContainer


class BaseStrategy:
    interface = None

    def __init__(self, strategy, strategy_interface=None):
        if strategy_interface:
            self.interface = strategy_interface
        self.strategy = self.interface(strategy)
        self.vault = interface.Vault(strategy.vault())

    def describe_base(self):
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

    def describe_strategy(self):
        return {}

    def describe(self):
        return {
            **self.describe_base(),
            **self.describe_strategy(),
        }


@dataclass
class StrategyUniswapPair(BaseStrategy):
    interface = interface.StrategyUniswapPair

    def describe_strategy(self):
        return {
            "wantPrice": self.strategy.wantPrice().to("ether"),
        }
