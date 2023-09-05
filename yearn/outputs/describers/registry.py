import asyncio
from collections import Counter

from brownie import chain
from y import Contract, Network

from yearn.outputs.describers.vault import VaultWalletDescriber

if chain.id == Network.Mainnet:
    yGov = Contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")

class RegistryWalletDescriber:
    def __init__(self):
        self.vault_describer = VaultWalletDescriber()

    async def active_vaults_at(self, registry: tuple, block=None):
        label, registry = registry
        active = await registry.active_vaults_at(block=block)
        if chain.id == Network.Mainnet:
            # [yGov] Doesn't count for this context
            active = [vault for vault in active if vault.vault != yGov]
        return active
        
    async def describe_wallets(self, registry: tuple, block=None):
        active_vaults = await self.active_vaults_at(registry, block=block)
        data = await asyncio.gather(*[self.vault_describer.describe_wallets(vault.vault.address, block=block) for vault in active_vaults])
        data = {vault.name: desc for vault, desc in zip(active_vaults, data) if desc}

        wallet_balances = Counter()
        for desc in data.values():
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
