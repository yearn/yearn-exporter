from yearn.multicall2 import fetch_multicall
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
        share_price, underlying, decimals = fetch_multicall(
            [vault, 'pricePerShare'],
            [vault, 'token'],
            [vault, 'decimals'],
            block=block
        )
        return [share_price / 10 ** decimals, underlying]
    if hasattr(vault, 'getPricePerFullShare'):
        share_price, underlying = fetch_multicall(
            [vault, 'getPricePerFullShare'],
            [vault, 'token'],
            block=block
        )
        return [share_price / 1e18, underlying]
