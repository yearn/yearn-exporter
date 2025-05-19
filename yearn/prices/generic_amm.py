
from functools import lru_cache
from typing import List, Optional

from brownie.convert.datatypes import EthAddress
from y.exceptions import PriceError, yPriceMagicError
from y.prices import magic

from yearn.multicall2 import fetch_multicall
from yearn.typing import Address, Block
from yearn.utils import contract


class GenericAmm:
    def __contains__(self, lp_token_address: Address) -> bool:
        return self.is_generic_amm(lp_token_address)

    @lru_cache(maxsize=None)
    def is_generic_amm(self, lp_token_address: Address) -> bool:
        try:
            token_contract = contract(lp_token_address)
            return all(hasattr(token_contract, attr) for attr in ['getReserves','token0','token1'])
        except Exception as e:
            if 'has not been verified' in str(e):
                return False
            raise
    
    def get_price(self, lp_token_address: Address, block: Optional[Block] = None) -> float:
        lp_token_contract = contract(lp_token_address)
        total_supply, decimals = fetch_multicall(*([lp_token_contract, attr] for attr in ['totalSupply','decimals']), block=block)
        total_supply_readable = total_supply / 10 ** decimals
        return self.get_tvl(lp_token_address, block) / total_supply_readable

    @lru_cache(maxsize=None)
    def get_tokens(self, lp_token_address: Address) -> List[EthAddress]:
        lp_token_contract = contract(lp_token_address)
        return fetch_multicall(*([lp_token_contract,attr] for attr in ('token0', 'token1')))
    
    def get_tvl(self, lp_token_address: Address, block: Optional[Block] = None) -> float:
        lp_token_contract = contract(lp_token_address)
        tokens = self.get_tokens(lp_token_address)
        reserves = lp_token_contract.getReserves(block_identifier=block)
        reserves = [reserves[i] / 10 ** contract(token).decimals() for i, token in enumerate(tokens)]
        prices = []
        for token in tokens:
            try:
                prices.append(magic.get_price(token, block = block))
            except yPriceMagicError as e:
                if not isinstance(e.exception, PriceError):
                    raise e
                prices.append(None)
        
        if all(price is None for price in prices):
            return None
        
        values = [reserve * price if price is not None else None for reserve, price in zip(reserves, prices)]

        # If we only know the value of one side, we can extrapolate for the other.
        if values[0] is None:
            values[0] = values[1]
        elif values[1] is None:
            values[1] = values[0]

        return sum(values)


generic_amm = GenericAmm()
