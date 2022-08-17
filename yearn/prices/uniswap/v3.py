import logging
import math
import json
from collections import defaultdict
from functools import cached_property
from itertools import cycle
from typing import Any, Dict, List, Optional, Tuple, Union

from brownie import Contract, chain, convert
from eth_abi.packed import encode_abi_packed
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.prices.constants import usdc, weth
from yearn.typing import Address, Block
from yearn.utils import Singleton, contract, contract_creation_block

logger = logging.getLogger(__name__)

class FeeTier(int):
    def __init__(self, v) -> None:
        super().__init__()

Path = List[Union[Address,FeeTier]]


# https://github.com/Uniswap/uniswap-v3-periphery/blob/main/deploys.md
UNISWAP_V3_FACTORY = '0x1F98431c8aD98523631AE4a59f267346ea31F984'
UNISWAP_V3_QUOTER = Contract.from_abi(
    name='Quoter',
    address='0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6',
    abi=json.load(open('interfaces/uniswap/UniswapV3Quoter.json'))
) # use direct abi from etherscan because the quoter is not verified on all chains (opti)
FEE_DENOMINATOR = 1_000_000
USDC_SCALE = 1e6

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
    Network.Optimism: {
        'factory': UNISWAP_V3_FACTORY,
        'quoter': UNISWAP_V3_QUOTER,
        'fee_tiers': [3000, 500, 10_000, 100]
    },
}


class UniswapV3(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in addresses:
            raise UnsupportedNetwork('uniswap v3 is not supported on this network')

        conf = addresses[chain.id]
        self.factory: Contract = contract(conf['factory'])
        self.quoter: Contract = conf['quoter']
        self.fee_tiers = [FeeTier(fee) for fee in conf['fee_tiers']]

    def __contains__(self, asset: Any) -> bool:
        return chain.id in addresses

    def encode_path(self, path: Path) -> bytes:
        types = [type for _, type in zip(path, cycle(['address', 'uint24']))]
        return encode_abi_packed(types, path)

    def undo_fees(self, path: Path) -> float:
        fees = [1 - fee / FEE_DENOMINATOR for fee in path if isinstance(fee, int)]
        return math.prod(fees)

    def get_price(self, token: Address, block: Optional[Block] = None) -> Optional[float]:
        if block and block < contract_creation_block(UNISWAP_V3_QUOTER):
            return None

        paths = self.get_paths(token)

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
            amount / self.undo_fees(path) / USDC_SCALE
            for amount, path in zip(results, paths)
            if amount
        ]
        return max(outputs) if outputs else None
    
    @cached_property
    def pools(self) -> Dict[Address,Dict[str,Union[str,int]]]:
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
    def pool_mapping(self) -> Dict[Address,Dict[Address,Address]]:
        '''
        Returns a dict {token_in:{pool:token_out}}
        '''
        pool_mapping: Dict[str,Dict[str,str]] = defaultdict(dict)
        for pool, attributes in self.pools.items():
            token0, token1, fee, tick_spacing = attributes.values()
            pool_mapping[token0][pool] = token1
            pool_mapping[token1][pool] = token0
        logger.info(f'Loaded {len(self.pools)} pools supporting {len(pool_mapping)} tokens on uniswap v3')
        return pool_mapping
    
    def deepest_pool_balance(self, token: Address, block: Optional[Block] = None) -> int:
        '''
        Returns the depth of the deepest pool for `token`, used to compary liquidity across dexes.
        '''
        token_contract = contract(token)
        pools = self.pool_mapping[token_contract.address]
        reserves = fetch_multicall(*[[token_contract,'balanceOf',pool] for pool in pools], block=block)

        deepest_pool_balance = 0
        for pool, balance in zip(pools, reserves):
            if balance > deepest_pool_balance:
                deepest_pool_balance = balance

        return deepest_pool_balance
    
    def get_paths(self, token: Address) -> List[Path]:
        token = convert.to_address(token)
        paths = [[token, fee, usdc] for fee in self.fee_tiers]

        if token == weth:
            return paths

        pools = self.pool_mapping[token]
        for pool in pools:
            token0, token1, fee, tick_spacing = self.pools[pool].values()
            if token == token0 and token1 == weth:
                paths += [[token0, fee, token1, tier, usdc] for tier in self.fee_tiers]
            elif token == token0:
                paths += [[token0, fee, token1, tier0, weth, tier1, usdc] for tier0, tier1 in self.tier_pairs]
            elif token == token1 and token0 == weth:
                paths += [[token1, fee, token0, tier, usdc] for tier in self.fee_tiers]
            elif token == token1:
                paths += [[token1, fee, token0, tier0, weth, tier1, usdc] for tier0, tier1 in self.tier_pairs]

        return paths
    
    @cached_property
    def tier_pairs(self) -> List[Tuple[FeeTier,FeeTier]]:
        '''
        Returns a list containing all possible pairs of fees for a 2 hop swap.
        '''
        return [
            (tier0,tier1)
            for tier0 in self.fee_tiers
            for tier1 in self.fee_tiers
        ]
        


uniswap_v3 = None
try:
    uniswap_v3 = UniswapV3()
except UnsupportedNetwork:
    pass
