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
        params = self.vault.strategies(self.strategy)
        return {
            "debtOutstanding": self.vault.debtOutstanding(self.strategy) / scale,
            "creditAvailable": self.vault.creditAvailable(self.strategy) / scale,
            "expectedReturn": self.vault.expectedReturn(self.strategy) / scale,
            "emergencyExit": self.strategy.emergencyExit(),
            "estimatedTotalAssets": self.strategy.estimatedTotalAssets() / scale,
            "performanceFee": params[0],
            "activation": params[1],
            "debtLimit": params[2] / scale,
            "rateLimit": params[3] / scale,
            "lastReport": params[4],
            "totalDebt": params[5] / scale,
            "totalReturns": params[6] / scale,
        }

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


@dataclass
class StrategyUniswapPairPickle(Strategy):
    def __init__(self, strategy):
        super().__init__(strategy, interface.StrategyUniswapPairPickle)

    def describe_strategy(self):
        return {
            "wantPrice": self.strategy.wantPrice().to("ether"),
        }


@dataclass
class LeveragedDaiCompStrategyV2(Strategy):
    def __init__(self, strategy):
        super().__init__(strategy, interface.LeveragedDaiCompStrategyV2)

    def describe_strategy(self):
        position = self.strategy.getCurrentPosition()
        return {
            "collateralTarget": self.strategy.collateralTarget().to("ether"),
            "getCompValInWei": self.strategy.getCompValInWei("1 ether").to("ether"),
            "getCurrentPosition_supply": position[0].to("ether"),
            "getCurrentPosition_borrow": position[1].to("ether"),
            "getblocksUntilLiquidation": self.strategy.getblocksUntilLiquidation(),
            "netBalanceLent": self.strategy.netBalanceLent().to("ether"),
            "predictCompAccrued": self.strategy.predictCompAccrued().to("ether"),
            "storedCollateralisation": self.strategy.storedCollateralisation().to("ether"),
        }
