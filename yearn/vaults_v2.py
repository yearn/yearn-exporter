from dataclasses import dataclass
from typing import List
from yearn.strategies import LeveragedDaiCompStrategyV2, Strategy, StrategyUniswapPairPickle

from brownie import interface
from brownie.network.contract import InterfaceContainer

from yearn import strategies


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class VaultV2:
    name: str
    vault: InterfaceContainer
    strategies: List[strategies.Strategy]

    def describe(self):
        scale = 10 ** self.vault.decimals()
        strats = [str(strat.strategy) for strat in self.strategies]
        strats.extend([ZERO_ADDRESS] * (40 - len(strats)))
        try:
            info = {
                "totalAssets": self.vault.totalAssets() / scale,
                "totalBalanceSheet": self.vault.totalBalanceSheet(strats) / scale,
                "maxAvailableShares": self.vault.maxAvailableShares() / scale,
                "pricePerShare": self.vault.pricePerShare() / scale,
                "debtOutstanding": self.vault.debtOutstanding() / scale,
                "creditAvailable": self.vault.creditAvailable() / scale,
                "expectedReturn": self.vault.expectedReturn() / scale,
                "totalSupply": self.vault.totalSupply() / scale,
                "emergencyShutdown": self.vault.emergencyShutdown(),
                "depositLimit": self.vault.depositLimit() / scale,
                "debtLimit": self.vault.debtLimit() / scale,
                "totalDebt": self.vault.totalDebt() / scale,
                "lastReport": self.vault.lastReport(),
                "managementFee": self.vault.managementFee(),
                "performanceFee": self.vault.performanceFee(),
                "strategies": {},
            }
        except ValueError as e:
            print("rekt", e)
            info = {"strategies": {}}
        for strat in self.strategies:
            info["strategies"][strat.name] = strat.describe()

        return info


VAULTS = [
    VaultV2(
        name="CRV",
        vault=interface.Vault("0x2832817633520BF0da1b57E2Fb7bb2Fba95014F9"),
        strategies=[
            strategies.Strategy("0xACb5eBaa9bAc72581b269077Ef4D0BA3Eefac2b7", interface.StrategyCreamCRV),
        ],
    ),
    VaultV2(
        name="DAI",
        vault=interface.Vault("0x9B142C2CDAb89941E9dcd0B6C1cf6dEa378A8D7C"),
        strategies=[
            strategies.LeveragedDaiCompStrategyV2("0x4C6e9d7E5d69429100Fcc8afB25Ea980065e2773"),
        ],
    ),
    VaultV2(
        name="WETH",
        vault=interface.Vault("0xF20731F26E98516dd83bb645DD757D33826a37b5"),
        strategies=[
            strategies.Strategy("0x97785a81B3505Ea9026b2aFFa709dfd0C9Ef24f6", interface.YearnWethCreamStratV2),
        ],
    ),
]
