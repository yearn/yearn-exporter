from collections import Counter
from typing import Union

from joblib.parallel import Parallel, delayed
from yearn.outputs.describers.vault import VaultWalletDescriber
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2
from collections import Counter


class RegistryWalletDescriber:
    def describe_wallets(self, registry: Union[RegistryV1, RegistryV2] , block=None):
        vaults = registry.active_vaults_at(block=block)
        describer = VaultWalletDescriber()
        data = Parallel(8,'threading')(delayed(describer.describe_wallets)(vault, block=block) for vault in vaults)
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