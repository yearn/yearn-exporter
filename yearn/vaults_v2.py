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
            info = {"strategies": {}}
        for strat in self.strategies:
            info["strategies"][strat.name] = strat.describe()

        info['token price'] = uniswap.token_price(self.vault.token())
        if 'totalAssets' in info:
            info['tvl'] = info['token price'] * info['totalAssets']

        return info


vaults = {
    "yusdcidle": "0x33bd0f9618cf38fea8f7f01e1514ab63b9bde64b",
    "devhugger": "0xFeD651936Af7e98F7F2A93c03B1E28a2DA7dfaD4",
    "apetrumpet": "0xba81fb02d5e7b94b341e82d1959c372590b852be",
    "icecreath2": "0x18c447b7Ad755379B8800F1Ef5165E8542946Afd",
    "wethcitadel": "0x18c447b7Ad755379B8800F1Ef5165E8542946Afd",
    "zzzvault": "0xCA6C9fB742071044247298Ea0dBd60b77586e1E8",
    "elcalfos": "0x19db27D2E9E4B780CF9A296D575aBbddEe1578DA",
    "sushirocket": "0x27Eb83254D900AB4F9b15d5652d913963FeC35e3",
    "daihard": "0xBFa4D8AA6d8a379aBFe7793399D3DdaCC5bBECBB",
    "usdc": "0xe2f6b9773bf3a015e2aa70741bde1498bdb9425b",
    # "yvsteth": "0x15a2B3CfaFd696e1C783FE99eed168b78a3A371e",
    "daiironbank": "0x07dbC20B84fF63F3cc542F6A22E5a71cbA5670A4",
    "wethmaker": "0x6392e8fa0588CB2DCb7aF557FdC9D10FDe48A325",
}


def get_vaults():
    return [VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in vaults.items()]
