import logging

from brownie import interface, web3, Contract
from brownie.network.contract import InterfaceContainer
from joblib import Parallel, delayed
from yearn.multicall2 import fetch_multicall
from yearn.utils import contract_creation_block
from yearn.v1.vaults import VaultV1

logger = logging.getLogger(__name__)


class Registry:
    def __init__(self):
        self.registry = interface.YRegistry(web3.ens.resolve("registry.ychad.eth"))
        addresses_provider = Contract("0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93")
        addresses_generator_v1_vaults = Contract(addresses_provider.addressById("ADDRESSES_GENERATOR_V1_VAULTS"))

        # NOTE: we assume no more v1 vaults are deployed
        self.vaults = [(vault_address, *self.registry.getVaultInfo(vault_address)) for vault_address in addresses_generator_v1_vaults.assetsAddresses()]

    def __repr__(self) -> str:
        return f"<Registry V1 vaults={len(self.vaults)}>"

    def describe(self, block=None):
        vaults = self.active_vaults_at(block)
        share_prices = fetch_multicall(*[[vault.vault, "getPricePerFullShare"] for vault in vaults], block=block)
        vaults = [vault for vault, share_price in zip(vaults, share_prices) if share_price]
        data = Parallel(8, "threading")(delayed(vault.describe)(block=block) for vault in vaults)
        return {vault.name: desc for vault, desc in zip(vaults, data)}

    def total_value_at(self, block=None):
        vaults = self.active_vaults_at(block)
        balances = fetch_multicall(*[[vault.vault, "balance"] for vault in vaults], block=block)
        # skip vaults with zero or erroneous balance
        vaults = [(vault, balance) for vault, balance in zip(vaults, balances) if balance]
        prices = Parallel(8, "threading")(delayed(vault.get_price)(block) for (vault, balance) in vaults)
        return {vault.name: balance * price / 10 ** vault.decimals for (vault, balance), price in zip(vaults, prices)}

    def active_vaults_at(self, block=None):
        vaults = list(self.vaults)
        if block:
            vaults = [vault for vault in vaults if contract_creation_block(str(vault.vault)) < block]
        return vaults
