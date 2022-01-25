import math
from itertools import cycle

from brownie import chain, interface
from eth_abi.packed import encode_abi_packed
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.prices.constants import usdc, weth
from yearn.utils import Singleton, contract, contract_creation_block

# https://github.com/Uniswap/uniswap-v3-periphery/blob/main/deploys.md
UNISWAP_V3_FACTORY = '0x1F98431c8aD98523631AE4a59f267346ea31F984'
UNISWAP_V3_QUOTER = '0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6'

# same addresses on all networks
addresses = {
    Network.Mainnet: {
        'factory': UNISWAP_V3_FACTORY,
        'quoter': UNISWAP_V3_QUOTER,
        'fee_tiers': [3000, 500, 10_000, 100],
    },
    Network.Arbitrum: {
        'factory': UNISWAP_V3_FACTORY,
        'quoter': UNISWAP_V3_QUOTER,
        'fee_tiers': [3000, 500, 10_000],
    },
}

FEE_DENOMINATOR = 1_000_000


class UniswapV3(metaclass=Singleton):
    def __init__(self):
        if chain.id not in addresses:
            raise UnsupportedNetwork('compound is not supported on this network')

        conf = addresses[chain.id]
        self.factory = contract(conf['factory'])
        self.quoter = contract(conf['quoter'])
        self.fee_tiers = conf['fee_tiers']

    def encode_path(self, path):
        types = [type for _, type in zip(path, cycle(['address', 'uint24']))]
        return encode_abi_packed(types, path)

    def undo_fees(self, path):
        fees = [1 - fee / FEE_DENOMINATOR for fee in path if isinstance(fee, int)]
        return math.prod(fees)

    def get_price(self, token, block=None):
        if block and block < contract_creation_block(UNISWAP_V3_QUOTER):
            return None

        if token == usdc:
            return 1

        paths = []
        if token != weth:
            paths += [
                [token, fee, weth, self.fee_tiers[0], usdc] for fee in self.fee_tiers
            ]

        paths += [[token, fee, usdc] for fee in self.fee_tiers]

        scale = 10 ** contract(token).decimals()

        results = fetch_multicall(
            *[
                [self.quoter, 'quoteExactInput', self.encode_path(path), scale]
                for path in paths
            ],
            block=block,
        )

        outputs = [
            amount / self.undo_fees(path) / 1e6
            for amount, path in zip(results, paths)
            if amount
        ]
        return max(outputs) if outputs else None


uniswap_v3 = None
try:
    uniswap_v3 = UniswapV3()
except UnsupportedNetwork:
    pass
