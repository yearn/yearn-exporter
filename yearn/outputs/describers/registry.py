import asyncio
from collections import Counter

from brownie import chain
from y.networks import Network

from yearn.outputs.describers.vault import VaultWalletDescriber
from yearn.utils import contract


class RegistryWalletDescriber:
    def __init__(self):
        self.vault_describer = VaultWalletDescriber()

    def active_vaults_at(self, registry: tuple, block=None):
        label, registry = registry
        active = [vault for vault in registry.active_vaults_at(block=block)]  
        if chain.id == Network.Mainnet:
            # [yGov] Doesn't count for this context
            active = [vault for vault in active if vault.vault != contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")]
        return active
        
    async def describe_wallets(self, registry: tuple, block=None):
        active_vaults = self.active_vaults_at(registry, block=block)
        data = await asyncio.gather(*[self.vault_describer.describe_wallets(vault.vault.address, block=block) for vault in active_vaults])
        data = {vault.name: desc for vault,desc in zip(active_vaults,data)}

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
