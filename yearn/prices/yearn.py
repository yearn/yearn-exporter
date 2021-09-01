from brownie import multicall

from yearn.utils import contract


def is_yearn_vault(token):
    vault = contract(token)
    return any(
        all(hasattr(vault, attr) for attr in kind)
        for kind in [
            ['pricePerShare', 'token', 'decimals'],
            ['getPricePerFullShare', 'token'],
        ]
    )


def get_price(token, block=None):
    # v1 vaults use getPricePerFullShare scaled to 18 decimals
    # v2 vaults use pricePerShare scaled to underlying token decimals
    vault = contract(token)
    if hasattr(vault, 'pricePerShare'):
        with multicall:
            share_price = vault.pricePerShare()
            underlying = vault.token()
            decimals = vault.decimals()
        return [share_price / 10 ** decimals, underlying]
    if hasattr(vault, 'getPricePerFullShare'):
        with multicall:
            share_price = vault.getPricePerFullShare()
            underlying = vault.token()
        return [share_price / 1e18, underlying]
