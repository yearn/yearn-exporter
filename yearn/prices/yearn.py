from brownie import Contract
from yearn.mutlicall import fetch_multicall


def is_yearn_vault(token):
    vault = Contract(token)
    return hasattr(vault, 'pricePerShare') or hasattr(vault, 'getPricePerFullShare')


def price(token, block=None):
    vault = Contract(token)
    price_per_share = 'pricePerShare' if hasattr(vault, 'pricePerShare') else 'getPricePerFullShare'
    share_price, underlying, decimals = fetch_multicall(
        [vault, price_per_share],
        [vault, 'underlying'],
        [vault, 'decimals'],
        block=block
    )
    return [share_price / 10 ** decimals, underlying]
