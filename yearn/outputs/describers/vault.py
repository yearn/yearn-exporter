from typing import Union
from yearn.outputs.postgres.postgres import PostgresInstance
from yearn.prices import magic
from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault as VaultV2

class VaultWalletDescriber:
    def wallets(self, vault_address, block=None):
        return self.wallet_balances(vault_address, block=block).keys()

    def wallet_balances(self, vault_address, block=None):
        return PostgresInstance().fetch_balances(vault_address, block=block)

    def describe_wallets(self, vault: Union[VaultV1, VaultV2], block=None):
        balances = self.wallet_balances(vault.vault.address, block=block)
        info = {
            'total wallets': len(set(wallet for wallet, bal in balances.items())),
            'active wallets': sum(1 if balance > 50 else 0 for wallet, balance in balances.items()),
            'wallet balances': {
                wallet: {
                    "token balance": float(bal),
                    "usd balance": float(bal) * self.get_price(vault, block=block)
                    } for wallet, bal in balances.items()
                }
        }
        return info

    def get_price(self, vault: Union[VaultV1, VaultV2], block=None):
        if isinstance(vault, VaultV1) and vault.name == "aLINK":
            return magic.get_price(self.vault.underlying(), block=block)
        else: 
            return magic.get_price(self.token, block=block)