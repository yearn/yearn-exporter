from dataclasses import dataclass
from typing import List

from brownie import interface
from brownie.network.contract import InterfaceContainer
from packaging import version

from yearn import strategies


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MIN_VERSION = version.parse("0.2.0")


@dataclass
class VaultV2:
    name: str
    vault: InterfaceContainer
    strategies: List[strategies.Strategy]

    def __post_init__(self):
        api_version = version.parse(self.vault.apiVersion())
        assert api_version >= MIN_VERSION, f"{self.name} unsupported vault api version {api_version}"

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
    # 0.2.2 DAI
    VaultV2(
        name="DAI",
        vault=interface.Vault("0xBFa4D8AA6d8a379aBFe7793399D3DdaCC5bBECBB"),
        strategies=[strategies.Strategy("0x5A9D49679319FCF3AcFe5559602Dbf31A221BaD6", interface.GenericLevCompFarm)],
    ),
    # 0.2.2 USDC
    VaultV2(
        name="USDC",
        vault=interface.Vault("0xe2F6b9773BF3A015E2aA70741Bde1498bdB9425b"),
        strategies=[strategies.Strategy("0x31576ac682ee0A15c48C4baC24c567f27CA1b7cD", interface.GenericLevCompFarm)],
    ),
]
