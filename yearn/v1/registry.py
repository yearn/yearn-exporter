import logging
import os
from collections import Counter

from brownie import Contract, interface, web3
from joblib import Parallel, delayed
from yearn.multicall2 import fetch_multicall
from yearn.utils import contract_creation_block, contract
from yearn.v1.vaults import VaultV1

logger = logging.getLogger(__name__)


class Registry:
    def __init__(self):
        self.registry = interface.YRegistry(web3.ens.resolve("registry.ychad.eth"))
        addresses_provider = contract("0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93")
        addresses_generator_v1_vaults = contract(addresses_provider.addressById("ADDRESSES_GENERATOR_V1_VAULTS"))

        # NOTE: we assume no more v1 vaults are deployed
        self.vaults = [VaultV1(vault_address, *self.registry.getVaultInfo(vault_address)) for vault_address in addresses_generator_v1_vaults.assetsAddresses()]
            
    def __repr__(self) -> str:
        return f"<Registry V1 vaults={len(self.vaults)}>"

    def describe(self, block=None):
        vaults = self.active_vaults_at(block)
        share_prices = fetch_multicall(*[[vault.vault, "getPricePerFullShare"] for vault in vaults], block=block)
        vaults = [vault for vault, share_price in zip(vaults, share_prices) if share_price]
        data = Parallel(8, "threading")(delayed(vault.describe)(block=block) for vault in vaults)
        return {vault.name: desc for vault, desc in zip(vaults, data)}

    def describe_wallets(self,block=None):
        vaults = self.active_vaults_at(block=block)
        data = Parallel(8,'threading')(delayed(vault.describe_wallets)(block=block) for vault in vaults)
        data = {vault.name: desc for vault,desc in zip(vaults,data)}

        wallet_balances = Counter()
        for vault, desc in data.items():
            for wallet, bals in desc['wallet balances'].items():
                wallet_balances[wallet] += bals["usd balance"]
        agg_stats = {
            "total wallets": len(wallet_balances),
            "active wallets": sum(1 if balance > 50 else 0 for wallet, balance in wallet_balances.items()),
            "wallets > $5k": sum(1 if balance > 5000 else 0 for wallet, balance in wallet_balances.items()),
            "wallets > $50k": sum(1 if balance > 50000 else 0 for wallet, balance in wallet_balances.items()),
            "wallet balances usd": wallet_balances,
        }
        data.update(agg_stats)
        return data

    def load_transfers(self):
        Parallel(8, "threading")(delayed(vault.load_transfers)() for vault in self.vaults)

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
