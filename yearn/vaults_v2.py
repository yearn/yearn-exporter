from dataclasses import dataclass
from typing import List

from brownie import interface, web3
from brownie.network.contract import InterfaceContainer
from packaging import version

from yearn import strategies
from yearn import uniswap
from yearn.mutlicall import fetch_multicall

VAULTS_EVENT_TOPIC = '0xce089905ba4a4d622553bcb5646fd23e895c256f0376eee04e99e61cec1dc7e8'
EXPERIMENTAL_VAULTS_EVENT_TOPIC = '0x57a9cdc2a05e05f66e76769bdbe88e21ec45d9ee0f97d4cb60395d4c75dcbcda'

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MIN_VERSION = version.parse("0.2.0")
VAULT_VIEWS = [
    "decimals",
    "totalAssets",
    "maxAvailableShares",
    "pricePerShare",
    "debtOutstanding",
    "creditAvailable",
    "expectedReturn",
    "totalSupply",
    "emergencyShutdown",
    "depositLimit",
    "debtRatio",
    "totalDebt",
    "lastReport",
    "managementFee",
    "performanceFee",
    "governance",
    "management",
    "guardian",
]

VAULT_VIEWS_SCALED = [
    "totalAssets",
    "maxAvailableShares",
    "pricePerShare",
    "debtOutstanding",
    "creditAvailable",
    "expectedReturn",
    "totalSupply",
    "depositLimit",
    "totalDebt",
]

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
            results = fetch_multicall(*[[self.vault, view] for view in VAULT_VIEWS])
            info = dict(zip(VAULT_VIEWS, results))
            for name in VAULT_VIEWS_SCALED:
                info[name] /= scale
            info['strategies'] = {}
        except ValueError as e:
            info = {"strategies": {}}
        for strat in self.strategies:
            info["strategies"][strat.name] = strat.describe()

        try:
            info["token price"] = uniswap.token_price(self.vault.token())
        except ValueError:
            info["token price"] = 0

        if "totalAssets" in info:
            info["tvl"] = info["token price"] * info["totalAssets"]

        return info


vaults = {
    "DAI 0.3.0": "0x19D3364A399d251E894aC732651be8B0E4e85001",
    "USDC 0.3.0": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
    "HEGIC 0.3.0": "0xe11ba472F74869176652C35D30dB89854b5ae84D",
    "curve.fi/steth 0.3.0": "0xdCD90C7f6324cfa40d7169ef80b12031770B4325",
    "WBTC 0.3.1": "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5",
    "WETH 0.3.2": "0xa9fE4601811213c340e850ea305481afF02f5b28",
    "curve.fi/seth 0.3.2": "0x986b4AFF588a109c09B50A03f42E4110E29D353F",
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
    return [
        VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in experimental_vaults.items()
    ]
