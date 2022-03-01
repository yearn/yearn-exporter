
from yearn.prices.magic import get_price
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
                    "usd balance": float(bal) * get_price(vault_address, block=block, return_price_during_vault_downtime=True)
                    } for wallet, bal in balances.items()
                }
            }
        info['active wallets'] = sum(1 if balances['usd balance'] > 50 else 0 for wallet, balances in info['wallet balances'].items())
        return info
