from brownie import chain
from yearn.cache import memory
from yearn.constants import BTC_LIKE, WRAPPED_GAS_COIN
from yearn.constants import ETH_LIKE as _ETH_LIKE
from yearn.networks import Network
from yearn.prices.balancer import balancer as bal
from yearn.prices.aave import aave
from yearn.prices.compound import compound
from yearn.prices.constants import stablecoins, weth
from yearn.prices.curve import curve
from yearn.prices.fixed_forex import fixed_forex
from yearn.prices.yearn import yearn_lens
from yearn.utils import contract

YFI_LIKE = {
    Network.Mainnet: {
        '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e',  # YFI
        '0xD0660cD418a64a1d44E9214ad8e459324D8157f1',  # WOOFY
    },
    Network.Fantom: {
        '0x29b0Da86e484E1C0029B56e817912d778aC0EC69',  # YFI
        '0xD0660cD418a64a1d44E9214ad8e459324D8157f1',  # WOOFY
    },
}.get(chain.id, set())

INTL_STABLECOINS = {
    Network.Mainnet: {
        '0xD71eCFF9342A5Ced620049e616c5035F1dB98620',  # sEUR
        '0xC581b735A1688071A1746c968e0798D642EDE491',  # EURT
        '0xdB25f211AB05b1c97D595516F45794528a807ad8',  # EURS
        '0x96E61422b6A9bA0e068B6c5ADd4fFaBC6a4aae27',  # ibEUR
    },
    Network.Fantom: {
        '',  #
    },
}.get(chain.id, set())

OTHER_LONG_TERM_ASSETS = {
    Network.Mainnet: {
        '0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44',  # KP3R
        '0xaf988afF99d3d0cb870812C325C588D8D8CB7De8',  # SLP (KP3R/ETH)
    },
    Network.Fantom: {
        '',  # 
    },
}.get(chain.id, set())

ETH_LIKE = _ETH_LIKE.union(
    {
        'ETH',
        weth,
        "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    }
)


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
    if bal.selector.get_balancer_for_pool(token):
        # should only be YLA # TODO figure this out
        bal_for_pool = bal.selector.get_balancer_for_pool(token)
        pool_tokens = set(
            str(_unwrap_token(coin)) for coin in bal_for_pool.get_tokens(token)
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
