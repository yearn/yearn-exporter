from typing import Union
from yearn.prices import magic
from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault as VaultV2

from yearn.outputs.postgres.utils import fetch_balances

class VaultWalletDescriber:
    def wallets(self, vault_address, block=None):
        return self.wallet_balances(vault_address, block=block).keys()

    def wallet_balances(self, vault_address, block=None):
        return fetch_balances(vault_address, block=block)

    def describe_wallets(self, vault_address, block=None):
        balances = self.wallet_balances(vault_address, block=block)
        info = {
            'total wallets': len(set(wallet for wallet, bal in balances.items())),
            'wallet balances': {
                wallet: {
                    "token balance": float(bal),
                    "usd balance": float(bal) * magic.get_price(vault_address, block=block)
                    } for wallet, bal in balances.items()
                }
            }
        info['active wallets'] = sum(1 if balances['usd balance'] > 50 else 0 for wallet, balances in info['wallet balances'].items())
        return info