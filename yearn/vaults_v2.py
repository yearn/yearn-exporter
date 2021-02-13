from dataclasses import dataclass
from typing import List

from brownie import interface, web3
from brownie.network.contract import InterfaceContainer
from packaging import version

from eth_event import get_log_topic,get_topic_map,decode_logs

from yearn import strategies
from yearn import uniswap

VAULTS_EVENT_TOPIC = '0xce089905ba4a4d622553bcb5646fd23e895c256f0376eee04e99e61cec1dc7e8'
EXPERIMENTAL_VAULTS_EVENT_TOPIC = '0x57a9cdc2a05e05f66e76769bdbe88e21ec45d9ee0f97d4cb60395d4c75dcbcda'

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MIN_VERSION = version.parse("0.2.0")

REGISTRY_DEPLOYMENT_BLOCK = 11563389

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
    "stETH 0.3.0": "0xdCD90C7f6324cfa40d7169ef80b12031770B4325",
    "WBTC 0.3.0": "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5",
}

def get_vault_addresses_from_events(topic):
    registry = web3.ens.resolve("v2.registry.ychad.eth")

    registry_v2 = interface.YRegistry2(registry)

    topic_map = get_topic_map(registry_v2.abi)

    event_filter = web3.eth.filter(
        {'fromBlock': REGISTRY_DEPLOYMENT_BLOCK, 'toBlock': 'latest', 'address': registry, 'topics': [
            topic]})

    event_logs = web3.eth.getFilterLogs(event_filter.filter_id)

    decoded = decode_logs(event_logs, topic_map)

    vaults = []

    for item in decoded:
        vault = {}
        for property in item['data']:
            vault[property['name']] = property['value']

        vaults.append(vault)

    vaults_flat = [v['vault'] for v in vaults]

    print("v2 vault addresses", vaults_flat)

    return vaults_flat

def get_vaults():

    vaults_flat = get_vault_addresses_from_events(VAULTS_EVENT_TOPIC)

    v2_vaults = []

    # fetch vault name and api version to construct the description
    for vault_address in vaults_flat:
        contract = interface.Vault(vault_address)
        name = contract.name()
        api_version = contract.apiVersion()
        description = name + ' ' + api_version
        vault_object = VaultV2(name=description, vault=contract, strategies=[])
        v2_vaults.append(vault_object)

    return v2_vaults
