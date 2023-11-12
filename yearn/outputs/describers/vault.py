
import asyncio
from concurrent.futures import ProcessPoolExecutor

from yearn.outputs.postgres.utils import fetch_balances
from yearn.prices.magic import _get_price

data_processes = ProcessPoolExecutor(5)


ACTIVE_WALLET_USD_THRESHOLD = 50.00

class VaultWalletDescriber:
    async def wallets(self, vault_address, block=None):
        return (await self.wallet_balances(vault_address, block=block)).keys()

    async def wallet_balances(self, vault_address, block=None):
        return await asyncio.get_event_loop().run_in_executor(data_processes, fetch_balances, vault_address, block)

    async def describe_wallets(self, vault_address, block=None):
        balances = await self.wallet_balances(vault_address, block=block)
        if not balances:
            return {}
        price = await _get_price(vault_address, block=block)
        info = {
            'total wallets': len(set(wallet for wallet, bal in balances.items())),
            'wallet balances': {
                wallet: {
                    "token balance": bal,
                    "usd balance": bal * price
                    } for wallet, bal in balances.items()
                }
            }
        info['active wallets'] = sum(1 if balances['usd balance'] > ACTIVE_WALLET_USD_THRESHOLD else 0 for balances in info['wallet balances'].values())
        return info
