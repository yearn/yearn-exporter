from brownie import Contract
from yearn.mutlicall import fetch_multicall


def is_yearn_vault(token):
    vault = Contract(token)
    return hasattr(vault, 'pricePerShare') or hasattr(vault, 'getPricePerFullShare')


def get_price(token, block=None):
    vault = Contract(token)
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
