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
    "WBTC 0.3.1": "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5",
}

experimental_vaults = {
    "sUSD Idle 0.3.1": "0x3466c90017F82DDA939B01E8DBd9b0f97AEF8DfC",
    # https://etherscan.io/address/0xA04fE40eD8a8a8d657E41276ec9e9Ee877675e34#code
    "WETH Gen Lender 0.3.1": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
    # https://etherscan.io/address/0xac5DA2Ca938A7328dE563D7d7209370e24BFd21e#code
    # "Egyptian God sETH/ETH 0.3.0": "0x0e880118C29F095143dDA28e64d95333A9e75A47",
    # https://etherscan.io/address/0x3B1a1AE6052ccD643a250fa843c1fB20F9246E1a#code
    "WETH Iron Lender 0.3.0": "0xED0244B688cF059f32f45E38A6ac6E479D6755f6",
    # https://etherscan.io/address/0xa35A4972D74d4B3e4486163066E5fFed6d62b213#code
    "WBTC 0.3.0": "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5",
    "yvSushi YFI-ETH 0.2.2": "0x27Eb83254D900AB4F9b15d5652d913963FeC35e3",
    # https://etherscan.io/address/0x3213a6389f3f4c287925a47A6D44fe1148FA0C0d#code
    "DEV Hugger 0.2.2": "0xFeD651936Af7e98F7F2A93c03B1E28a2DA7dfaD4",
    # https://etherscan.io/address/0x2E949057Ce561BAA9d494895235ACCe310a73FDB#code
    # https://etherscan.io/address/0x38a97cB34FCE4FAc87D1F7f8639e3341978613b6#code
    "USDc Idle 0.2.2": "0x33bd0f9618cf38fea8f7f01e1514ab63b9bde64b",
    # https://etherscan.io/address/0xc29CBe79F1a35a6AA00Df70851E36B14316Ab990#code
    "Mushroom Worker 0.3.0": "0x0e8A7717A4FD7694682E7005957dD5d7598bF14A"
    # https://etherscan.io/address/0xE5dc99Cbf841A6721781E592214674A87a1A70BC#code
    # Left out Lido St. Ether Vault, and ApeTrump Vault
}

def get_vaults():
    # TODO: read from registry
    return [VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in vaults.items()]

def get_experimental_vaults():
    return [VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in experimental_vaults.items()]