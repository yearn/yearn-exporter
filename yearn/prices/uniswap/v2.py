from brownie import Contract, chain
from cachetools.func import lru_cache, ttl_cache
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.prices.constants import usdc, weth
from yearn.utils import Singleton, contract

# NOTE insertion order defines priority, higher priority get queried first.
addresses = {
    Network.Mainnet: [
        {
            'name': 'sushiswap',
            'factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac',
            'router': '0xD9E1CE17F2641F24AE83637AB66A2CCA9C378B9F',
        },
        {
            'name': 'uniswap',
            'factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f',
            'router': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
        },
    ],
    Network.Fantom: [
        {
            'name': 'spookyswap',
            'factory': '0x152eE697f2E276fA89E96742e9bB9aB1F2E61bE3',
            'router': '0xF491e7B69E4244ad4002BC14e878a34207E38c29',
        },
        {
            'name': 'spiritswap',
            'factory': '0xEF45d134b73241eDa7703fa787148D9C9F4950b0',
            'router': '0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52',
        },
    ],
}


class UniswapV2:
    name: str
    factory: str
    router: str

    def __init__(self, name, factory, router):
        self.name = name
        self.factory = contract(factory)
        self.router = contract(router)

    def __repr__(self):
        return f'<UniswapV2 name={self.name} factory={self.factory} router={self.router}>'

    @ttl_cache(ttl=600)
    def get_price(self, token_in, token_out=usdc, block=None):
        """
        Calculate a price based on Uniswap Router quote for selling one `token_in`.
        Always uses intermediate WETH pair.
        """
        tokens = [contract(str(token)) for token in [token_in, token_out]]
        try:
            amount_in = 10 ** tokens[0].decimals()
        except AttributeError:
            return None
        path = (
            [token_in, token_out]
            if weth in (token_in, token_out)
            else [token_in, weth, token_out]
        )
        fees = 0.997 ** (len(path) - 1)
        try:
            quote = self.router.getAmountsOut(amount_in, path, block_identifier=block)
            amount_out = quote[-1] / 10 ** tokens[1].decimals()
            return amount_out / fees
        except ValueError:
            return None
    
    @ttl_cache(ttl=600)
    def lp_price(self, address, block=None):
        """Get Uniswap/Sushiswap LP token price."""
        pair = contract(address)
        token0, token1, supply, reserves = fetch_multicall(
            [pair, "token0"],
            [pair, "token1"],
            [pair, "totalSupply"],
            [pair, "getReserves"],
            block=block,
        )
        tokens = [Contract(token) for token in [token0, token1]]
        scales = [10 ** token.decimals() for token in tokens]
        prices = [self.get_price(token, block=block) for token in tokens]
        supply = supply / 1e18
        if None in prices or supply == 0:
            return None
        balances = [
            res / scale * price for res, scale, price in zip(reserves, scales, prices)
        ]
        return sum(balances) / supply


class UniswapV2Multiplexer(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('uniswap v2 is not supported on this network')
        self.uniswaps = [
            UniswapV2(conf['name'], conf['factory'], conf['router'])
            for conf in addresses[chain.id]
        ]

    def __contains__(self, asset):
        return chain.id in addresses

    def get_price(self, token, block=None):
        for exchange in self.uniswaps:
            price = exchange.get_price(token, block=block)
            if price:
                return price

    @lru_cache(maxsize=None)
    def is_uniswap_pool(self, address):
        try:
            return contract(address).factory() in [x.factory for x in self.uniswaps]
        except (ValueError, OverflowError, AttributeError):
            pass
        return False

    @ttl_cache(ttl=600)
    def lp_price(self, token, block=None):
        pair = contract(token)
        factory = pair.factory()
        try:
            exchange = next(x for x in self.uniswaps if x.factory == factory)
        except StopIteration:
            return None
        else:
            return exchange.lp_price(token, block)


uniswap_v2 = None
try:
    uniswap_v2 = UniswapV2Multiplexer()
except UnsupportedNetwork:
    pass
