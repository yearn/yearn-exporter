import math
from itertools import cycle

from eth_abi.packed import encode_abi_packed

from yearn.multicall2 import fetch_multicall
from yearn.utils import contract

# https://github.com/Uniswap/uniswap-v3-periphery/blob/main/deploys.md
UNISWAP_V3_FACTORY = '0x1F98431c8aD98523631AE4a59f267346ea31F984'
UNISWAP_V3_QUOTER = '0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6'

WETH = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
USDC = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'

FEE_TIERS = [500, 3000, 10_000]
DEFAULT_FEE = 3000
FEE_DENOMINATOR = 1_000_000
USDC_SCALE = 10 ** 6


def encode_path(path):
    types = [type for _, type in zip(path, cycle(['address', 'uint24']))]
    return encode_abi_packed(types, path)


def undo_fees(path):
    fees = [1 - fee / FEE_DENOMINATOR for fee in path if isinstance(fee, int)]
    return math.prod(fees)


def get_price(asset, block=None):
    if asset == USDC:
        return 1

    paths = [[asset, fee, USDC] for fee in FEE_TIERS]
    if asset != WETH:
        paths += [[asset, fee, WETH, DEFAULT_FEE, USDC] for fee in FEE_TIERS]

    scale = 10 ** contract(asset).decimals()
    quoter = contract(UNISWAP_V3_QUOTER)

    results = fetch_multicall(
        *[[quoter, 'quoteExactInput', encode_path(path), scale] for path in paths],
        block=block,
    )

    outputs = [
        amount / undo_fees(path) / USDC_SCALE
        for amount, path in zip(results, paths)
        if amount
    ]
    return max(outputs) if outputs else None
