from cachetools.func import ttl_cache

from yearn.utils import contract, contract_creation_block

registry = contract('0x5C08bC10F45468F18CbDC65454Cbd1dd2cB1Ac65')


@ttl_cache(ttl=3600)
def get_fixed_forex_markets():
    return registry.forex()


def is_fixed_forex(token):
    return token in get_fixed_forex_markets()


@ttl_cache(maxsize=None, ttl=600)
def get_price(token, block=None):
    if block is None or block >= contract_creation_block(str(registry)):
        return registry.price(token, block_identifier=block) / 1e18
    else:
        # fallback method for before registry deployment
        oracle = contract(registry.oracle())
        ctoken = registry.cy(token)
        return oracle.getUnderlyingPrice(ctoken, block_identifier=block) / 1e18
