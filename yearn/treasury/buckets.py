from yearn.cache import memory
from yearn.constants import WRAPPED_GAS_COIN
from yearn.prices import balancer as bal
from yearn.prices.aave import aave
from yearn.prices.compound import compound
from yearn.prices.constants import stablecoins, weth
from yearn.prices.curve import curve
from yearn.prices.fixed_forex import fixed_forex
from yearn.prices.yearn import yearn_lens
from yearn.treasury.constants import (BTC_LIKE, ETH_LIKE, INTL_STABLECOINS,
                                      OTHER_LONG_TERM_ASSETS, YFI_LIKE)
from yearn.typing import Address
from yearn.utils import contract


def get_token_bucket(token) -> str:
    token = str(token)
    try:
        token = str(_unwrap_token(token))
    except ValueError as e:
        if str(e).startswith('Source for') and str(e).endswith('has not been verified'):
            return 'Other short term assets'
        raise
    
    if _is_stable(token):
        return 'Cash & cash equivalents'
    if token in ETH_LIKE:
        return 'ETH'
    if token in BTC_LIKE:
        return 'BTC'
    if token in YFI_LIKE:
        return 'YFI'
    if token in OTHER_LONG_TERM_ASSETS:
        return 'Other long term assets'
    return 'Other short term assets'


@memory.cache()
def _unwrap_token(token) -> str:
    '''
    Unwraps the base
    '''
    if str(token) in ["ETH", "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"]:
        return token

    if yearn_lens.is_yearn_vault(token):
        return _unwrap_token(contract(token).token())
    if token in curve:
        pool = curve.get_pool(token)
        pool_tokens = set(
            str(_unwrap_token(coin)) for coin in curve.get_underlying_coins(pool)
        )
        return _pool_bucket(pool_tokens)
    if bal.balancer and bal.balancer.is_balancer_pool(token):  # should only be YLA # TODO figure this out
        pool_tokens = set(
            str(_unwrap_token(coin)) for coin in contract(token).getCurrentTokens()
        )
        return _pool_bucket(pool_tokens)
    if aave and token in aave:
        return aave.atoken_underlying(token)
    if compound and token in compound:
        try:
            return contract(token).underlying()
        except AttributeError:
            return WRAPPED_GAS_COIN
    return token


def _pool_bucket(pool_tokens: set) -> str:
    if pool_tokens < BTC_LIKE:
        return list(BTC_LIKE)[0]
    if pool_tokens < ETH_LIKE:
        return list(ETH_LIKE)[0]
    if pool_tokens < stablecoins.keys():
        return list(stablecoins.keys())[0]
    if pool_tokens < INTL_STABLECOINS:
        return list(INTL_STABLECOINS)[0]

def _is_stable(token: Address) -> bool:
    return any([
        token in stablecoins,
        token in INTL_STABLECOINS,
        (fixed_forex and token in fixed_forex),
    ])
