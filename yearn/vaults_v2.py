from dataclasses import dataclass
from typing import List

from brownie import interface
from brownie.network.contract import InterfaceContainer
from packaging import version

from yearn import strategies
from yearn import uniswap


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
                "maxAvailableShares": self.vault.maxAvailableShares() / scale,
                "pricePerShare": self.vault.pricePerShare() / scale,
                "debtOutstanding": self.vault.debtOutstanding() / scale,
                "creditAvailable": self.vault.creditAvailable() / scale,
                "expectedReturn": self.vault.expectedReturn() / scale,
                "totalSupply": self.vault.totalSupply() / scale,
                "emergencyShutdown": self.vault.emergencyShutdown(),
                "depositLimit": self.vault.depositLimit() / scale,
                "debtRatio": self.vault.debtRatio(),
                "totalDebt": self.vault.totalDebt() / scale,
                "lastReport": self.vault.lastReport(),
                "managementFee": self.vault.managementFee(),
                "performanceFee": self.vault.performanceFee(),
                "strategies": {},
            }
        except ValueError as e:
            info = {"strategies": {}}
        for strat in self.strategies:
            info["strategies"][strat.name] = strat.describe()

        info["token price"] = uniswap.token_price(self.vault.token())
        if "totalAssets" in info:
            info["tvl"] = info["token price"] * info["totalAssets"]

        return info


vaults = {
    "DAI 0.3.0": "0x19D3364A399d251E894aC732651be8B0E4e85001",
    "USDC 0.3.0": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
    "HEGIC 0.3.0": "0xe11ba472F74869176652C35D30dB89854b5ae84D",
    "stETH 0.3.0": "0xdCD90C7f6324cfa40d7169ef80b12031770B4325",
    "WBTC 0.3.0": "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5",
}
experimental_vaults = {
    "DAI 0.3.0": "0x19D3364A399d251E894aC732651be8B0E4e85001",
    "USDC 0.3.0": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
    "HEGIC 0.3.0": "0xe11ba472F74869176652C35D30dB89854b5ae84D",
    "stETH 0.3.0": "0xdCD90C7f6324cfa40d7169ef80b12031770B4325",
    "WBTC 0.3.0": "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5",
}

def get_vaults():
    # TODO: read from registry
    return [VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in vaults.items()]
