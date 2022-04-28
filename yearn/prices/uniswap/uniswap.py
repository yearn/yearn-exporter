
from typing import Any, Dict, Optional, Union

from yearn.prices.uniswap.v1 import UniswapV1, uniswap_v1
from yearn.prices.uniswap.v2 import UniswapV2Multiplexer, uniswap_v2
from yearn.prices.uniswap.v3 import UniswapV3, uniswap_v3
from yearn.typing import Address, Block

Uniswap = Union[UniswapV1,UniswapV2Multiplexer,UniswapV3]

UNISWAPS: Dict[str,Optional[Uniswap]] = {
    'v1': uniswap_v1,
    'v2': uniswap_v2,
    'v3': uniswap_v3
}

class UniswapVersionMultiplexer:
    def __init__(self) -> None:
        self.uniswaps: Dict[str,Uniswap] = {version: uniswap for version, uniswap in UNISWAPS.items() if uniswap is not None}
    
    def __contains__(self, token: Any) -> bool:
        return len(self.uniswaps) > 0

    def get_price(self, token: Address, block: Optional[Block] = None) -> Optional[float]:
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

uniswaps = UniswapVersionMultiplexer()
