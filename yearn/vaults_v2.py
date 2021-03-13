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
    "YFI 0.3.2": "0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1",
    "1INCH 0.3.2": "0xB8C3B7A2A618C552C23B1E4701109a9E756Bab67",
}

experimental_vaults = {
    "Iron Llama 0.3.2": "0x27b7b1ad7288079A66d12350c828D3C00A6F07d7",
    "Pool With Us 0.3.2": "0x2F194Da57aa855CAa02Ea3Ab991fa5d38178B9e6",
    "True Idle 0.3.2": "0x49b3E44e54b6220aF892DbA48ae45F1Ea6bC4aE9",
    "Idle Tether 0.3.2": "0xAf322a2eDf31490250fdEb0D712621484b09aBB6",
    "Data Aave 0.3.2": "0xac1c90b9c76d56ba2e24f3995f7671c745f8f308",
    "Full Metal Farmer 0.3.2": "0x56A5Fd5104a4956898753dfb060ff32882Ae0eb4",
    "Creamy Swords SNX 0.3.1": "0x7356f09c294cb9c6428ac7327b24b0f29419c181",
    "sUSD Idle 0.3.1": "0x3466c90017F82DDA939B01E8DBd9b0f97AEF8DfC",
    "WETH Gen Lender 0.3.1": "0xac333895ce1a73875cf7b4ecdc5a743c12f3d82b",
    "WETH Iron Lender 0.3.0": "0xED0244B688cF059f32f45E38A6ac6E479D6755f6",
    "Mushroom Worker 0.3.0": "0x0e8A7717A4FD7694682E7005957dD5d7598bF14A"
}


def get_vaults():
    # TODO: read from registry
    return [VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in vaults.items()]


def get_experimental_vaults():
    return [
        VaultV2(name=name, vault=interface.Vault(vault), strategies=[]) for name, vault in experimental_vaults.items()
    ]
