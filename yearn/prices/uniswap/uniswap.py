
from typing import Dict, List, Optional, Union

from yearn.prices.uniswap.v1 import UniswapV1, uniswap_v1
from yearn.prices.uniswap.v2 import UniswapV2Multiplexer, uniswap_v2
from yearn.prices.uniswap.v3 import UniswapV3, uniswap_v3

Uniswap = Union[UniswapV1,UniswapV2Multiplexer,UniswapV3]

class UniswapVersionMultiplexer:
    def __init__(self) -> None:
        self.uniswaps: Dict[str,Uniswap] = {
            'v1': uniswap_v1,
            'v2': uniswap_v2,
            'v3': uniswap_v3
        }
        self.uniswaps = {version: uniswap for version, uniswap in self.uniswaps.items() if uniswap is not None}
        self.try_order: List[str] = ['v2','v3','v1']


    def get_price(self, token: str, block: Optional[int]) -> Optional[float]:
        for version in self.try_order:
            if version not in self.uniswaps:
                continue
            price = self.uniswaps[version].get_price(token, block)
            if price is None:
                continue
            return price
        return None
    
    def deepest_uniswap(self, token_in: str, block: Optional[int]) -> Optional[Uniswap]:
        deepest_uniswap = None
        deepest_uniswap_balance = 0
        uniswaps = [uniswap for uniswap in self.uniswaps.values() if uniswap is not None]
        for uniswap in uniswaps


uniswaps = UniswapVersionMultiplexer()