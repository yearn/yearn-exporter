from brownie import Contract, interface
from brownie.exceptions import ContractNotFound
from cachetools.func import ttl_cache
from yearn.cache import memory
from yearn.multicall2 import fetch_multicall
from yearn.prices.constants import weth, usdc

FACTORIES = {
    "uniswap": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    "sushiswap": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
}
ROUTERS = {
    "uniswap": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "sushiswap": "0xD9E1CE17F2641F24AE83637AB66A2CCA9C378B9F",
}
FACTORY_TO_ROUTER = {FACTORIES[name]: ROUTERS[name] for name in FACTORIES}


@ttl_cache(ttl=600)
def get_price(token_in, token_out=usdc, router="uniswap", block=None):
    """
    Calculate a price based on Uniswap Router quote for selling one `token_in`.
    Always uses intermediate WETH pair.
    """
    tokens = [Contract(str(token)) for token in [token_in, token_out]]
    amount_in = 10 ** tokens[0].decimals()
    path = [token_in, token_out] if weth in (token_in, token_out) else [token_in, weth, token_out]
    fees = 0.997 ** (len(path) - 1)
    if router in ROUTERS:
        router = interface.UniswapRouter(ROUTERS[router])
    try:
        quote = router.getAmountsOut(amount_in, path, block_identifier=block)
        amount_out = quote[-1] / 10 ** tokens[1].decimals()
        return amount_out / fees
    except ValueError:
        pass


@ttl_cache(ttl=600)
def get_price_v1(asset, block=None):
    factory = Contract("0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95")
    try:
        asset = Contract(asset)
        exchange = interface.UniswapV1Exchange(factory.getExchange(asset))
        eth_bought = exchange.getTokenToEthInputPrice(10 ** asset.decimals(), block_identifier=block)
        exchange = interface.UniswapV1Exchange(factory.getExchange(usdc))
        usdc_bought = exchange.getEthToTokenInputPrice(eth_bought, block_identifier=block) / 1e6
        fees = 0.997 ** 2
        return usdc_bought / fees
    except (ContractNotFound, ValueError) as e:
        pass


@memory.cache()
def is_uniswap_pool(address):
    try:
        return Contract(address).factory() in FACTORY_TO_ROUTER
    except (ValueError, OverflowError, AttributeError):
        pass
    return False


@ttl_cache(ttl=600)
def lp_price(address, block=None):
    """ Get Uniswap/Sushiswap LP token price. """
    pair = Contract(address)
    factory, token0, token1, supply, reserves = fetch_multicall(
        [pair, "factory"],
        [pair, "token0"],
        [pair, "token1"],
        [pair, "totalSupply"],
        [pair, "getReserves"],
        block=block
    )
    router = FACTORY_TO_ROUTER[factory]
    tokens = [Contract(token) for token in [token0, token1]]
    scales = [10 ** token.decimals() for token in tokens]
    prices = [get_price(token, router=router, block=block) for token in tokens]
    supply = supply / 1e18
    balances = [res / scale * price for res, scale, price in zip(reserves, scales, prices)]
    return sum(balances) / supply
