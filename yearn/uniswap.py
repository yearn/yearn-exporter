from brownie import interface

factory = interface.UniswapFactory('0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f')
router = interface.UniswapRouter('0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D')
weth = interface.ERC20('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
usdc = interface.ERC20('0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48')
dai = interface.ERC20('0x6B175474E89094C44Da98b954EedeAC495271d0F')


def price_router(token_in, token_out):
    """
    Calculate a price based on Uniswap Router quote for selling one `token_in`.
    Always uses intermediate WETH pair.
    """
    amount_in = 10 ** interface.ERC20(token_in).decimals()
    path = [token_in, token_out] if weth in (token_in, token_out) else [token_in, weth, token_out]
    quote = router.getAmountsOut(amount_in, path)
    amount_out = quote[-1] / 10 ** interface.ERC20(token_out).decimals()
    return amount_out


def price_direct(token_in, token_out):
    """
    Calculate a price based on Uniswap Pair reserves.
    Only supports direct pairs.
    """
    pair = interface.UniswapPair(factory.getPair(token_in, token_out))
    reserves = dict(zip([pair.token0(), pair.token1()], pair.getReserves()[:2]))
    reserves_in = reserves[token_in] / 10 ** interface.ERC20(token_in).decimals()
    reserves_out = reserves[token_out] / 10 ** interface.ERC20(token_out).decimals()
    return reserves_out / reserves_in
