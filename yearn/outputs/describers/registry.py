from collections import Counter

from joblib.parallel import Parallel, delayed
from yearn.outputs.describers.vault import VaultWalletDescriber
from yearn.utils import contract


class RegistryWalletDescriber:
    def active_vaults_at(self, registry: tuple, block=None):
        label, registry = registry
        active = [vault for vault in registry.active_vaults_at(block=block) if vault.vault != contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")]  # [yGov] Doesn't count for this context
        return active
        
    def describe_wallets(self, registry: tuple, block=None):
        describer = VaultWalletDescriber()
        active_vaults = self.active_vaults_at(registry, block=block)
        data = Parallel(8,'threading')(delayed(describer.describe_wallets)(vault.vault.address, block=block) for vault in active_vaults)
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
