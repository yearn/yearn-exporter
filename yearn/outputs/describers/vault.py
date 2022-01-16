import logging

from yearn.outputs.postgres.utils import fetch_balances
from yearn.prices import magic
from yearn.utils import contract

logger = logging.getLogger(__name__)

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
                    "usd balance": float(bal) * _get_price(vault_address, block=block)
                    } for wallet, bal in balances.items()
                }
            }
        info['active wallets'] = sum(1 if balances['usd balance'] > 50 else 0 for wallet, balances in info['wallet balances'].items())
        return info
    
def _get_price(token_address, block=None):
    try: return magic.get_price(token_address, block=block)
    except TypeError as e:
        if token_address == '0xec0d8D3ED5477106c6D4ea27D90a60e594693C90' and block <= 11645697:
            return 0 # NOTE: yGUSD `share_price` returns `None` because balance() reverts due to hack
        elif str(e) == "unsupported operand type(s) for /: 'NoneType' and 'float'" and token_address == '0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab':
            # NOTE: There was an accounting error that had to be fixed manually
            LAST_BLOCK_BEFORE_ACCOUNTING_ERR = 12429262
            token = contract(token_address)
            ppfs = token.getPricePerFullShare(block_identifier=LAST_BLOCK_BEFORE_ACCOUNTING_ERR) / 1e18
            want_price = magic.get_price(token.token(),block=block)
            return ppfs * want_price
        else:
            token = contract(token_address)
            try:
                token.getPricePerFullShare(block_identifier=block)
            except ValueError as e:
                if 'division by zero' in str(e) and token.totalSupply(block_identifier=block) == 0:
                    return magic.get_price(token.token(block_identifier=block),block=block) # NOTE: This runs when totalSupply() == 0 during early testing
        logger.warn(f'address: {token_address}')
        logger.warn(f'block: {block}')
        raise
