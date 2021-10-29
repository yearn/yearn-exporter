from functools import cached_property
from brownie import Contract, chain

from cachetools.func import ttl_cache
from yearn.utils import Singleton


SCALE = 10 ** 18


class Band(metaclass=Singleton):
    @cached_property
    def oracle(self):
        if chain.id == '250':
            return Contract('0x56E2898E0ceFF0D1222827759B56B28Ad812f92F')
        else:
            raise ValueError(f'chain {chain.id} not supported')

    def get_price(self, asset, block=None):
        asset_symbol = Contract(asset).symbol()
        return self.oracle.getReferenceData(asset_symbol, 'USDC', block_identifier=block)[0] / SCALE


band = Band()


@ttl_cache(maxsize=None, ttl=600)
def get_price(asset, block=None):
    try:
        return band.get_price(asset, block)
    except (KeyError, ValueError):
        return None
