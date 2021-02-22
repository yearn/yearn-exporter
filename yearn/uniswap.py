from brownie import Contract, interface
from cachetools import LRUCache, TTLCache, cached

from yearn import curve
from yearn.constants import VAULT_ALIASES
from yearn.mutlicall import fetch_multicall

factory = interface.UniswapFactory("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")

FACTORIES = {
    "uniswap": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    "sushiswap": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
}
ROUTERS = {
    "uniswap": interface.UniswapRouter("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
    "sushiswap": interface.UniswapRouter("0xD9E1CE17F2641F24AE83637AB66A2CCA9C378B9F"),
}
FACTORY_TO_ROUTER = {FACTORIES[name]: ROUTERS[name] for name in FACTORIES}
# these tokens are assumed to be priced at 1, the price is not queried
STABLECOINS = {
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "usdc",
    "0x0000000000085d4780B73119b644AE5ecd22b376": "tusd",
    "0x6B175474E89094C44Da98b954EedeAC495271d0F": "dai",
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "usdt",
    "0x4Fabb145d64652a948d72533023f6E7A623C7C53": "busd",
    "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51": "susd",
}
weth = interface.ERC20("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
usdc = interface.ERC20("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
dai = interface.ERC20("0x6B175474E89094C44Da98b954EedeAC495271d0F")
wbtc = interface.ERC20("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599")


def price_router(token_in, token_out=usdc, router=None):
    """
    Calculate a price based on Uniswap Router quote for selling one `token_in`.
    Always uses intermediate WETH pair.
    """
    tokens = [interface.ERC20(token) for token in [token_in, token_out]]
    amount_in = 10 ** tokens[0].decimals()
    path = [token_in, token_out] if weth in (token_in, token_out) else [token_in, weth, token_out]
    for router in ['sushiswap', 'uniswap']:
        router = ROUTERS[router]
        try:
            quote = router.getAmountsOut(amount_in, path)
            amount_out = quote[-1] / 10 ** tokens[1].decimals()
            return amount_out
        except ValueError:
            pass


def price_direct(token_in, token_out):
    """
    Calculate a price based on Uniswap Pair reserves.
    Only supports direct pairs.
    """
    pair = interface.UniswapPair(factory.getPair(token_in, token_out))
    reserves = dict(zip([pair.token0(), pair.token1()], pair.getReserves()))
    reserves_in = reserves[token_in] / 10 ** interface.ERC20(token_in).decimals()
    reserves_out = reserves[token_out] / 10 ** interface.ERC20(token_out).decimals()
    return reserves_out / reserves_in


@cached(LRUCache(1000))
def is_uniswap_pool(address):
    try:
        return interface.UniswapPair(address).factory() in FACTORY_TO_ROUTER
    except (ValueError, OverflowError):
        pass
    return False


def uniswap_lp_price(address):
    """ Get Uniswap LP token price. """
    pair = interface.UniswapPair(address)
    router = FACTORY_TO_ROUTER[pair.factory()]
    tokens = [interface.ERC20(token) for token in [pair.token0(), pair.token1()]]
    scales = [10 ** token.decimals() for token in tokens]
    prices = [price_router(token, router=router) for token in tokens]
    supply = pair.totalSupply() / 1e18
    return sum(reserve / scale * price for reserve, scale, price in zip(pair.getReserves(), scales, prices)) / supply


@cached(TTLCache(1, 86400))
def get_compound_markets():
    comptroller = Contract('0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B')
    return comptroller.getAllMarkets()


@cached(LRUCache(1000))
def is_compound_market(addr):
    comptroller = Contract('0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B')
    return addr in comptroller.getAllMarkets()


def token_price(token):
    # stablecoin => 1
    if token in STABLECOINS:
        return 1
    # eth => weth
    if token == '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE':
        token = weth
    # yearn vault => underlying price * price per share
    if str(token) in VAULT_ALIASES:
        token = interface.yVault(token)
        underlying, share_price = fetch_multicall(
            [token, 'token'],
            [token, 'getPricePerFullShare'],
        )
        return token_price(underlying) * share_price / 1e18
    # curve lp => first component price * virtual price
    if curve.is_curve_lp_token(token):
        return curve.get_base_price(token) * curve.get_virtual_price(token)
    # compound ctoken => underlying price * exchange rate
    if is_compound_market(token):
        token = interface.CErc20(token)
        underlying, exchange_rate, decimals = fetch_multicall(
            [token, 'underlying'],
            [token, 'exchangeRateCurrent'],
            [token, 'decimals'],
        )
        exchange_rate /= 1e18
        under_decimals = interface.ERC20(underlying).decimals()
        return token_price(underlying) * exchange_rate * 10 ** (decimals - under_decimals)
    # uniswap or sushi lp => share of reserves
    if is_uniswap_pool(token):
        return uniswap_lp_price(token)
    # try to get quote from sushiswap or uniswap
    return price_router(token)
