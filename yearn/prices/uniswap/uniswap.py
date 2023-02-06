import logging
import os
from typing import Any, Dict, Optional, Union

from brownie import chain, convert
from y.networks import Network

from yearn.constants import WRAPPED_GAS_COIN
from yearn.prices import constants
from yearn.prices.uniswap.v1 import UniswapV1, uniswap_v1
from yearn.prices.uniswap.v2 import UniswapV2Multiplexer, uniswap_v2
from yearn.prices.uniswap.v3 import UniswapV3, uniswap_v3
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import contract

logger = logging.getLogger(__name__)
Uniswap = Union[UniswapV1,UniswapV2Multiplexer,UniswapV3]

UNISWAPS: Dict[str,Optional[Uniswap]] = {
    'v1': uniswap_v1
}
# disable v2 and v3 pools during debugging
if os.getenv("DEBUG", None):
    logger.info("DEBUG is on, disabling uniswap v2 and v3 pool generation for faster debugging.")
else:
    UNISWAPS['v2'] = uniswap_v2
    UNISWAPS['v3'] = uniswap_v3

class UniswapVersionMultiplexer:
    def __init__(self) -> None:
        self.uniswaps: Dict[str,Uniswap] = {version: uniswap for version, uniswap in UNISWAPS.items() if uniswap is not None}
    
    def __contains__(self, token: Any) -> bool:
        return len(self.uniswaps) > 0

    def get_price(self, token: AddressOrContract, block: Optional[Block] = None) -> Optional[float]:
        token = convert.to_address(token)

        # NOTE Following our usual logic with WETH is a big no-no. Too many calls.
        if token in [constants.weth, WRAPPED_GAS_COIN]:
            return self._early_exit_for_gas_coin(token, block=block)

        deepest_uniswap = self.deepest_uniswap(token, block)
        if deepest_uniswap:
            return deepest_uniswap.get_price(token, block=block)
        return None

    def deepest_uniswap(self, token_in: Address, block: Optional[Block] = None) -> Optional[Uniswap]:
        deepest_uniswap = None
        deepest_uniswap_balance = 0
        for uniswap in self.uniswaps.values():
            deepest_pool_balance = uniswap.deepest_pool_balance(token_in, block)
            if deepest_pool_balance and deepest_pool_balance > deepest_uniswap_balance:
                deepest_uniswap = uniswap
                deepest_uniswap_balance = deepest_pool_balance
        return deepest_uniswap
    
    def _early_exit_for_gas_coin(self, token: Address, block: Optional[Block] = None) -> Optional[float]:
        ''' We use this to bypass the liquidity checker for ETH prior to deployment of the chainlink feed. '''
        amount_in = 1e18
        path = [token, constants.usdc]
        best_market = {
            Network.Mainnet: "uniswap",
            Network.Fantom: "spookyswap",
            Network.Gnosis: "sushiswap",
        }[chain.id]
        for uni in self.uniswaps['v2'].uniswaps:
            if uni.name != best_market:
                continue
            quote = uni.router.getAmountsOut(amount_in, path, block_identifier=block)[-1]
            quote /= 10 ** contract(constants.usdc).decimals()
            fees = 0.997 ** (len(path) - 1)
            return quote / fees

uniswaps = UniswapVersionMultiplexer()
