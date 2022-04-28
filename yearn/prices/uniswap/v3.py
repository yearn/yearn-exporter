import logging
import math
from collections import defaultdict
from functools import cached_property
from itertools import cycle
from typing import Dict, Optional, Union

from brownie import chain
from eth_abi.packed import encode_abi_packed
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.prices.constants import usdc, weth
from yearn.utils import Singleton, contract, contract_creation_block

logger = logging.getLogger(__name__)

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

    def __contains__(self, asset):
        return chain.id in addresses

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

        try:
            scale = 10 ** contract(token).decimals()
        except AttributeError:
            return None

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
    
    @cached_property
    def pools(self) -> Dict[str,Dict[str,Union[str,int]]]:
        '''
        Returns a dict {pool:{attr:value}} where attr is one of: 'token0', 'token1', 'fee', 'tick spacing'
        '''
        logger.info(f'Fetching pools for uniswap v3 on {Network.label()}. If this is your first time running yearn-exporter, this can take a while. Please wait patiently...')
        PoolCreated = ['0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118']
        events = decode_logs(get_logs_asap(self.factory.address, PoolCreated))
        return {
            event['pool']: {
                'token0': event['token0'],
                'token1': event['token1'],
                'fee': event['fee'],
                'tick spacing': event['tickSpacing']
            }
            for event in events
        }
    
    @cached_property
    def pool_mapping(self) -> Dict[str,Dict[str,str]]:
        '''
        Returns a dict {token_in:{pool:token_out}}
        '''
        pool_mapping = defaultdict(dict)
        for pool, attributes in self.pools.items():
            token0, token1, fee, tick_spacing = attributes.values()
            pool_mapping[token0][pool] = token1
            pool_mapping[token1][pool] = token0
        logger.info(f'Loaded {len(self.pools)} pools supporting {len(pool_mapping)} tokens on uniswap v3')
        return pool_mapping
    
    def deepest_pool_balance(self, token: str, block: Optional[int] = None) -> int:
        '''
        Returns the depth of the deepest pool for `token`, used to compary liquidity across dexes.
        '''
        token = contract(token)
        pools = self.pool_mapping[token.address]
        reserves = fetch_multicall(*[[token,'balanceOf',pool] for pool in pools], block=block)

        deepest_pool_balance = 0
        for pool, balance in zip(pools, reserves):
            if balance > deepest_pool_balance:
                deepest_pool_balance = balance

        return deepest_pool_balance


uniswap_v3 = None
try:
    uniswap_v3 = UniswapV3()
except UnsupportedNetwork:
    pass
