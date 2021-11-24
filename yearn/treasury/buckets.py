from brownie import Contract
from yearn.cache import memory
from yearn.constants import BTC_LIKE, ETH_LIKE as _ETH_LIKE
from ypricemagic.balancer import is_balancer_pool
from yearn.prices.compound import is_compound_market
from yearn.prices.constants import STABLECOINS, weth
from yearn.prices.fixed_forex import is_fixed_forex
from ypricemagic.aave import is_atoken_v1, is_atoken_v2
from ypricemagic.curve import get_underlying_coins, is_curve_lp_token
from ypricemagic.yearn import is_yearn_vault

YFI_LIKE = {
    '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e',  # YFI
    '0xD0660cD418a64a1d44E9214ad8e459324D8157f1',  # WOOFY
}

INTL_STABLECOINS = {
    '0xD71eCFF9342A5Ced620049e616c5035F1dB98620',  # sEUR
    '0xC581b735A1688071A1746c968e0798D642EDE491',  # EURT
    '0xdB25f211AB05b1c97D595516F45794528a807ad8',  # EURS
    '0x96E61422b6A9bA0e068B6c5ADd4fFaBC6a4aae27',  # ibEUR
}

OTHER_LONG_TERM_ASSETS = {
    '0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44',  # KP3R
    '0xaf988afF99d3d0cb870812C325C588D8D8CB7De8',  # SLP (KP3R/ETH)
}

ETH_LIKE = _ETH_LIKE.union(
    {
        'ETH',
        weth,
        "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    }
)


def get_token_bucket(token) -> str:
    token = str(token)
    token = str(_unwrap_token(token))
    if (
        token in STABLECOINS or token in INTL_STABLECOINS or is_fixed_forex(token)
    ):  # or token == '0x9ba60bA98413A60dB4C651D4afE5C937bbD8044B': # yla
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

    if is_yearn_vault(token):
        return _unwrap_token(Contract(token).token())
    if is_curve_lp_token(token):
        pool_tokens = set(
            str(_unwrap_token(coin)) for coin in get_underlying_coins(token)
        )
        return _pool_bucket(pool_tokens)
    if is_balancer_pool(token):  # should only be YLA # TODO figure this out
        pool_tokens = set(
            str(_unwrap_token(coin)) for coin in Contract(token).getCurrentTokens()
        )
        return _pool_bucket(pool_tokens)
    if is_atoken_v1(token):
        return Contract(token).underlyingAssetAddress()
    if is_atoken_v2(token):
        return Contract(token).UNDERLYING_ASSET_ADDRESS()
    if is_compound_market(token):
        try:
            return Contract(token).underlying()
        except AttributeError:
            return weth
    return token


def _pool_bucket(pool_tokens: set) -> str:
    if pool_tokens < BTC_LIKE:
        return list(BTC_LIKE)[0]
    if pool_tokens < ETH_LIKE:
        return list(ETH_LIKE)[0]
    if pool_tokens < STABLECOINS.keys():
        return list(STABLECOINS.keys())[0]
    if pool_tokens < INTL_STABLECOINS:
        return list(INTL_STABLECOINS)[0]
