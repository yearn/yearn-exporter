
from functools import lru_cache

from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.utils import contract


class GenericAmm:
    def __contains__(self, lp_token_address: str) -> bool:
        return self.is_generic_amm(lp_token_address)

    @lru_cache(maxsize=None)
    def is_generic_amm(self, lp_token_address: str) -> bool:
        try:
            token_contract = contract(lp_token_address)
            return all(hasattr(token_contract, attr) for attr in ['getReserves','token0','token1'])
        except Exception as e:
            if 'has not been verified' in str(e):
                return False
            raise
    
    def get_price(self, lp_token_address: str, block: int = None) -> float:
        lp_token_contract = contract(lp_token_address)
        total_supply, decimals = fetch_multicall(*[[lp_token_contract, attr] for attr in ['totalSupply','decimals']], block=block)
        total_supply_readable = total_supply / 10 ** decimals
        return self.get_tvl(lp_token_address, block) / total_supply_readable

    @lru_cache(maxsize=None)
    def get_tokens(self, lp_token_address: str, block: int = None):
        lp_token_contract = contract(lp_token_address)
        return fetch_multicall(*[[lp_token_contract,attr] for attr in ['token0', 'token1']])
    
    def get_tvl(self, lp_token_address: str, block: int = None) -> float:
        lp_token_contract = contract(lp_token_address)
        tokens = self.get_tokens(lp_token_address)
        reserves = lp_token_contract.getReserves(block_identifier=block)
        reserves = [reserves[i] / 10 ** contract(token).decimals() for i, token in enumerate(tokens)]
        return sum(reserve * magic.get_price(token) for token, reserve in zip(tokens, reserves))


generic_amm = GenericAmm()
