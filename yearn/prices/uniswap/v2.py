import logging
from collections import defaultdict
from functools import cached_property
from typing import Any, Dict, List, Optional

from brownie import Contract, chain, convert, interface
from brownie.convert.datatypes import EthAddress
from brownie.exceptions import EventLookupError, VirtualMachineError
from cachetools.func import lru_cache, ttl_cache
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.prices.constants import stablecoins, usdc, weth
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)

# NOTE insertion order defines priority, higher priority get queried first.
addresses: List[Dict[str,str]] = {
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
    Network.Gnosis: [
        {
            'name': 'sushiswap',
            'factory': '0xc35DADB65012eC5796536bD9864eD8773aBc74C4',
            'router': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
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
        {
            'name': 'sushiswap',
            'factory': '0xc35DADB65012eC5796536bD9864eD8773aBc74C4',
            "router": '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        }
    ],
    Network.Arbitrum: [
        {
            'name': 'sushiswap',
            'factory': '0xc35DADB65012eC5796536bD9864eD8773aBc74C4',
            'router': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        },
        {
            'name': 'fraxswap',
            'factory': '0x5Ca135cB8527d76e932f34B5145575F9d8cbE08E',
            'router': '0xc2544A32872A91F4A553b404C6950e89De901fdb',
        },
    ],
    Network.Optimism: [
        {
            'name': 'zipswap',
            'factory': '0x8BCeDD62DD46F1A76F8A1633d4f5B76e0CDa521E',
            'router': '0xE6Df0BB08e5A97b40B21950a0A51b94c4DbA0Ff6',

        }
    ]
}

EXCLUDED_POOLS = {
    Network.Optimism: [
        "0x6b8EF8E744Ad206D52F143560f49c1e5D60797B7", # unverified CRV-USDC on zigswap
    ]
}


class CantFindSwapPath(Exception):
    pass


class UniswapV2:
    def __init__(self, name: str, factory: Address, router: Address) -> None:
        self.name = name
        self.factory: Contract = contract(factory)
        self.router: Contract = contract(router)

        # Used for internals
        self._depth_cache: Dict[Address,Dict[Block,int]] = defaultdict(dict)

    def __repr__(self) -> str:
        return f'<UniswapV2 name={self.name} factory={self.factory} router={self.router}>'

    @ttl_cache(ttl=600)
    def get_price(self, token_in: AddressOrContract, token_out: AddressOrContract = usdc, block: Optional[Block] = None) -> Optional[float]:
        """
        Calculate a price based on Uniswap Router quote for selling one `token_in`.
        Always uses intermediate WETH pair.
        """
        token_in = convert.to_address(token_in)
        token_out = convert.to_address(token_out)
        tokens = [contract(str(token)) for token in [token_in, token_out]]
        amount_in = 10 ** tokens[0].decimals()
        path = None
        if token_out in stablecoins:
            try:
                path = self.get_path_to_stables(token_in)
            except CantFindSwapPath:
                pass
        
        if not path:
            path = (
                [token_in, token_out]
                if weth in (token_in, token_out)
                else [token_in, weth, token_out]
            )
            
        fees = 0.997 ** (len(path) - 1)
        try:
            quote = self.router.getAmountsOut(amount_in, path, block_identifier=block)
            amount_out = quote[-1] / 10 ** contract(str(path[-1])).decimals()
            return amount_out / fees
        except ValueError as e:
            okay_errs = ['execution reverted', 'No data was returned - the call likely reverted']
            if not any([err in str(e) for err in okay_errs]):
                raise
            return None
        except VirtualMachineError as e:
            okay_errs = ['INSUFFICIENT_INPUT_AMOUNT','revert: twamm out of date']
            if not any([err in str(e) for err in okay_errs]):
                raise
            return None
    
    @ttl_cache(ttl=600)
    def lp_price(self, address: Address, block: Optional[Block] = None) -> Optional[float]:
        """Get Uniswap/Sushiswap LP token price."""
        pair = contract(address)
        token0, token1, supply, reserves = fetch_multicall(
            [pair, "token0"],
            [pair, "token1"],
            [pair, "totalSupply"],
            [pair, "getReserves"],
            block=block,
        )
        tokens = [contract(token) for token in [token0, token1]]
        scales = [10 ** token.decimals() for token in tokens]
        prices = [self.get_price(token, block=block) for token in tokens]
        supply = supply / 1e18
        if None in prices or supply == 0:
            return None
        balances = [
            res / scale * price for res, scale, price in zip(reserves, scales, prices)
        ]
        return sum(balances) / supply


    def excluded_pools(self):
        if chain.id in EXCLUDED_POOLS:
            return EXCLUDED_POOLS[chain.id]
        else:
            return []


    @cached_property
    def pools(self) -> Dict[Address,Dict[Address,Address]]:
        '''
        Returns a dictionary with all pools
        {pool:{'token0':token0,'token1':token1}}
        '''
        logger.info(f'Fetching pools for {self.name} on {Network.label()}. If this is your first time running yearn-exporter, this can take a while. Please wait patiently...')
        PairCreated = ['0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9']
        events = decode_logs(get_logs_asap(self.factory.address, PairCreated))
        try:
            pairs = {
                event['']: {
                    convert.to_address(event['pair']): {
                        'token0':convert.to_address(event['token0']),
                        'token1':convert.to_address(event['token1']),
                    }
                }
                for event in events
            }
            pools = {pool: tokens for i, pair in pairs.items() for pool, tokens in pair.items()}
        except EventLookupError:
            pairs, pools = {}, {}
        
        all_pairs_len = self.factory.allPairsLength()
        if len(pairs) < all_pairs_len:
            logger.debug("Oh no! looks like your node can't look back that far. Checking for the missing pools...")
            poolids_your_node_couldnt_get = [i for i in range(all_pairs_len) if i not in pairs]
            logger.debug(f'missing poolids: {poolids_your_node_couldnt_get}')
            pools_your_node_couldnt_get = fetch_multicall(*[[self.factory,'allPairs',i] for i in poolids_your_node_couldnt_get])
            token0s = fetch_multicall(*[[contract(pool), 'token0'] for pool in pools_your_node_couldnt_get if pool not in self.excluded_pools()])
            token1s = fetch_multicall(*[[contract(pool), 'token1'] for pool in pools_your_node_couldnt_get if pool not in self.excluded_pools()])
            additional_pools = {
                convert.to_address(pool): {
                    'token0':convert.to_address(token0),
                    'token1':convert.to_address(token1),
                }
                for pool, token0, token1 in zip(pools_your_node_couldnt_get,token0s,token1s)
            }
            pools.update(additional_pools)

        return pools
    
    @cached_property
    def pool_mapping(self) -> Dict[Address,Dict[Address,Address]]:
        '''
        Returns a dictionary with all available combinations of {token_in:{pool:token_out}}
        '''
        pool_mapping: Dict[Address,Dict[Address,Address]] = defaultdict(dict)

        for pool, tokens in self.pools.items():
            token0, token1 = tokens.values()
            pool_mapping[token0][pool] = token1
            pool_mapping[token1][pool] = token0
        logger.info(f'Loaded {len(self.pools)} pools supporting {len(pool_mapping)} tokens on {self.name}')
        return pool_mapping
    
    def pools_for_token(self, token_address: Address) -> Dict[Address,Address]:
        try:
            return self.pool_mapping[token_address]
        except KeyError:
            return {}

    def deepest_pool(self, token_address: AddressOrContract, block: Optional[Block] = None, _ignore_pools: List[Address] = []) -> Optional[EthAddress]:
        token_address = convert.to_address(token_address)
        if token_address == weth or token_address in stablecoins:
            return self.deepest_stable_pool(token_address)
        pools = self.pools_for_token(token_address)
        reserves = fetch_multicall(*[[contract(pool),'getReserves'] for pool in pools], block=block, require_success=False)

        deepest_pool = None
        deepest_pool_balance = 0
        for pool, reserves in zip(pools,reserves):
            if reserves is None or pool in _ignore_pools:
                continue
            if token_address == self.pools[pool]['token0']:
                reserve = reserves[0]
            elif token_address == self.pools[pool]['token1']:
                reserve = reserves[1]
            if reserve > deepest_pool_balance: 
                deepest_pool = pool
                deepest_pool_balance = reserve
        return deepest_pool
    
    def deepest_stable_pool(self, token_address: AddressOrContract, block: Optional[Block] = None) -> Optional[EthAddress]:
        token_address = convert.to_address(token_address)
        pools = {pool: paired_with for pool, paired_with in self.pools_for_token(token_address).items() if paired_with in stablecoins}
        reserves = fetch_multicall(*[[contract(pool), 'getReserves'] for pool in pools], block=block, require_success=False)

        deepest_stable_pool = None
        deepest_stable_pool_balance = 0
        for pool, reserves in zip(pools, reserves):
            if reserves is None:
                continue
            if token_address == self.pools[pool]['token0']:
                reserve = reserves[0]
            elif token_address == self.pools[pool]['token1']:
                reserve = reserves[1]
            if reserve > deepest_stable_pool_balance:
                deepest_stable_pool = pool
                deepest_stable_pool_balance = reserve
        return deepest_stable_pool
    
    def get_path_to_stables(self, token_address: AddressOrContract, block: Optional[Block] = None, _loop_count: int = 0, _ignore_pools: List[Address] = []) -> List[AddressOrContract]:
        if _loop_count > 10:
            raise CantFindSwapPath
        
        token_address = convert.to_address(token_address)
        path = [token_address]
        deepest_pool = self.deepest_pool(token_address, block, _ignore_pools)
        if deepest_pool:
            paired_with = self.pool_mapping[token_address][deepest_pool]
            deepest_stable_pool = self.deepest_stable_pool(token_address, block)
            if deepest_stable_pool and deepest_pool == deepest_stable_pool:
                last_step = self.pool_mapping[token_address][deepest_stable_pool]
                path.append(last_step)
                return path

            if path == [token_address]:
                try: path.extend(
                        self.get_path_to_stables(
                            paired_with,
                            block=block, 
                            _loop_count=_loop_count+1, 
                            _ignore_pools=_ignore_pools + [deepest_pool]
                        )
                    )
                except CantFindSwapPath: pass

        if path == [token_address]: raise CantFindSwapPath(f'Unable to find swap path for {token_address} on {Network.label()}')

        return path


class UniswapV2Multiplexer(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in addresses:
            raise UnsupportedNetwork('uniswap v2 is not supported on this network')
        self.uniswaps = [
            UniswapV2(conf['name'], conf['factory'], conf['router'])
            for conf in addresses[chain.id]
        ]

    def __contains__(self, asset: Any) -> bool:
        return chain.id in addresses

    def get_price(self, token: AddressOrContract, block: Optional[Block] = None) -> Optional[float]:
        deepest_uniswap = self.deepest_uniswap(token, block)
        if deepest_uniswap:
            return deepest_uniswap.get_price(token, block=block)
        return None

    @lru_cache(maxsize=None)
    def is_uniswap_pool(self, address: Address) -> bool:
        try:
            return contract(address).factory() in [x.factory for x in self.uniswaps]
        except (ValueError, OverflowError, AttributeError):
            pass
        return False

    @ttl_cache(ttl=600)
    def lp_price(self, token: Address, block: Optional[Block] = None) -> Optional[float]:
        pair = contract(token)
        factory = pair.factory()
        try:
            exchange = next(x for x in self.uniswaps if x.factory == factory)
        except StopIteration:
            return None
        else:
            return exchange.lp_price(token, block)
    
    @lru_cache(maxsize=100)
    def deepest_uniswap(self, token_in: AddressOrContract, block: Optional[Block] = None) -> Optional[UniswapV2]:
        token_in = convert.to_address(token_in)
        pool_to_uniswap = {pool: uniswap for uniswap in self.uniswaps for pool in uniswap.pools_for_token(token_in)}
        reserves = fetch_multicall(*[[interface.UniswapPair(pool), 'getReserves'] for pool in pool_to_uniswap], block=block)
        
        deepest_uniswap = None
        deepest_uniswap_balance = 0
        for uniswap, pool, reserves in zip(pool_to_uniswap.values(), pool_to_uniswap.keys(),reserves):
            if reserves is None:
                continue
            if token_in == uniswap.pools[pool]['token0']:
                reserve = reserves[0]
            elif token_in == uniswap.pools[pool]['token1']:
                reserve = reserves[1]
            if reserve > deepest_uniswap_balance: 
                deepest_uniswap = uniswap
                deepest_uniswap_balance = reserve
        
        if deepest_uniswap:
            if block is not None:
                deepest_uniswap._depth_cache[token_in][block] = deepest_uniswap_balance
            return deepest_uniswap
        return None
    
    def deepest_pool_balance(self, token_in: AddressOrContract, block: Optional[Block] = None) -> Optional[Block]:
        if block is None:
            block = chain.height
        token_in = convert.to_address(token_in)
        deepest_uniswap = self.deepest_uniswap(token_in, block)
        if deepest_uniswap:
            return deepest_uniswap._depth_cache[token_in][block]
        return None


uniswap_v2 = None
try:
    uniswap_v2 = UniswapV2Multiplexer()
except UnsupportedNetwork:
    pass
