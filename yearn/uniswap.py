from brownie import interface

factory = interface.UniswapFactory("0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f")

FACTORIES = {
    "uniswap": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    "sushiswap": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
}
ROUTERS = {
    "uniswap": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "sushiswap": "0xD9E1CE17F2641F24AE83637AB66A2CCA9C378B9F",
}
FACTORY_TO_ROUTER = {FACTORIES[name]: ROUTERS[name] for name in FACTORIES}
STABLECOINS = {
    "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "tusd": "0x0000000000085d4780B73119b644AE5ecd22b376",
    "dai": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "usdt": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
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
    router = interface.UniswapRouter(router or ROUTERS["uniswap"])
    amount_in = 10 ** tokens[0].decimals()
    path = [token_in, token_out] if weth in (token_in, token_out) else [token_in, weth, token_out]
    quote = router.getAmountsOut(amount_in, path)
    amount_out = quote[-1] / 10 ** tokens[1].decimals()
    return amount_out


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


def token_price(token):
    if token in STABLECOINS:
        return 1
    # stETH Curve LP
    if token == "0x06325440D014e39736583c165C2963BA99fAf14E":
        virtual_price = interface.CurveSwap("0xDC24316b9AE028F1497c275EB9192a3Ea0f67022").get_virtual_price() / 1e18
        return price_router(weth) * virtual_price
    if is_uniswap_pool(token):
        return uniswap_lp_price(token)
    return price_router(token)
