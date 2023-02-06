
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional
from y.prices.magic import get_price_async
from y.datatypes import AnyAddressType, Block
from yearn.outputs.postgres.utils import fetch_balances
from yearn.prices.incidents import INCIDENTS

data_processes = ProcessPoolExecutor(5)

async def _get_price(token: AnyAddressType, block: Optional[Block]) -> float:
    try:
        return await get_price_async(token, block)
    except:
        for incident in INCIDENTS[token]:
            if incident['start'] <= block <= incident['end']:
                return incident['result']
        raise

class VaultWalletDescriber:
    async def wallets(self, vault_address, block=None):
        return (await self.wallet_balances(vault_address, block=block)).keys()

    async def wallet_balances(self, vault_address, block=None):
        return asyncio.get_event_loop().run_in_executor(data_processes, fetch_balances, vault_address, block=block)

    async def describe_wallets(self, vault_address, block=None):
        balances, price = await asyncio.gather(
            self.wallet_balances(vault_address, block=block),
            _get_price(vault_address, block=block),
        )
        info = {
            'total wallets': len(set(wallet for wallet, bal in balances.items())),
            'wallet balances': {
                wallet: {
                    "token balance": float(bal),
                    "usd balance": float(bal) * price
                    } for wallet, bal in balances.items()
                }
            }
        info['active wallets'] = sum(1 if balances['usd balance'] > 50 else 0 for wallet, balances in info['wallet balances'].items())
        return info
