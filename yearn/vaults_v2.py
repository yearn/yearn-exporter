from dataclasses import dataclass
from typing import List

from brownie import interface
from brownie.network.contract import InterfaceContainer


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass
class VaultV2:
    name: str
    vault: InterfaceContainer
    strategies: List[InterfaceContainer]

    def describe(self):
        scale = 10 ** self.vault.decimals()
        strats = [str(strat) for strat in self.strategies]
        strats.extend([ZERO_ADDRESS] * (40 - len(strats)))
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
        for strat in self.strategies:
            params = self.vault.strategies(strat)
            info["strategies"][strat._name] = {
                "debtOutstanding": self.vault.debtOutstanding(strat) / scale,
                "creditAvailable": self.vault.creditAvailable(strat) / scale,
                "expectedReturn": self.vault.expectedReturn(strat) / scale,
                "emergencyExit": strat.emergencyExit(),
                "estimatedTotalAssets": strat.estimatedTotalAssets() / scale,
                "expectedReturn": strat.expectedReturn() / scale,
                "outstanding": strat.outstanding() / scale,
                "reserve": strat.reserve() / scale,
                "performanceFee": params[0],
                "activation": params[1],
                "debtLimit": params[2] / scale,
                "rateLimit": params[3] / scale,
                "lastReport": params[4],
                "totalDebt": params[5] / scale,
                "totalReturns": params[6] / scale,
            }

        return info


VAULTS = [
    VaultV2(
        name="CRV",
        vault=interface.Vault("0x2832817633520BF0da1b57E2Fb7bb2Fba95014F9"),
        strategies=[
            interface.StrategyCreamCRV("0xACb5eBaa9bAc72581b269077Ef4D0BA3Eefac2b7"),
        ],
    ),
    VaultV2(
        name="UNI-V2 WBTC/WETH",
        vault=interface.Vault("0x7095472D01a964E50349AA12cE4d5263Af77E0d7"),
        strategies=[
            interface.StrategyUniswapPairPickle("0xC102658e4a81261eD5eaA6dC0ef87A56A6B1084F"),
        ],
    ),
]
