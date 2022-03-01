import logging

from brownie import chain
from yearn.exceptions import PriceError
from yearn.networks import Network
from yearn.outputs.postgres.utils import fetch_balances
from yearn.prices import magic

logger = logging.getLogger(__name__)

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
                    "usd balance": float(bal) * _get_price(vault_address, block=block)
                    } for wallet, bal in balances.items()
                }
            }
        info['active wallets'] = sum(1 if balances['usd balance'] > 50 else 0 for wallet, balances in info['wallet balances'].items())
        return info


def _get_price(token_address, block=None):
    try:
        return magic.get_price(token_address, block=block)
    except PriceError as e:
        if chain.id == Network.Mainnet and block:
            # crvAAVE vault state was broken due to an incident, return a post-fix price
            # https://github.com/yearn/yearn-security/blob/master/disclosures/2021-05-13.md
            if token_address == '0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab' and 12430455 <= block <= 12430661:
                return 1.091553
            # GUSD vault state was broken due to an incident, return a post-fix price
            # https://github.com/yearn/yearn-security/blob/master/disclosures/2021-01-17.md
            elif token_address == '0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab' and 11603873 <= block <= 11645877:
                return 0

        logger.exception(e)
        raise e
