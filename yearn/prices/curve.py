from brownie import Contract, ZERO_ADDRESS
from yearn.cache import memory
from cachetools.func import ttl_cache

# curve registry documentation https://curve.readthedocs.io/registry-address-provider.html
address_provider = Contract('0x0000000022D53366457F9d5E68Ec105046FC4383')
curve_registry = Contract(address_provider.get_address(0))
metapool_factory = Contract(address_provider.get_address(3))

# fold underlying tokens into one of the basic tokens
BASIC_TOKENS = {
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # dai
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # weth
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # eth
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # wbtc
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620",  # seur
    "0x514910771AF9Ca656af840dff83E8264EcF986CA",  # link
}


@memory.cache()
def get_pool(token):
    if set(metapool_factory.get_underlying_coins(token)) != {ZERO_ADDRESS}:
        return token
    return curve_registry.get_pool_from_lp_token(token)


@memory.cache()
def is_curve_lp_token(token):
    return get_pool(token) != ZERO_ADDRESS


@memory.cache()
def get_underlying_coins(token):
    pool = get_pool(token)
    coins = curve_registry.get_underlying_coins(pool)
    if set(coins) == {ZERO_ADDRESS}:
        coins = metapool_factory.get_underlying_coins(token)
    return [coin for coin in coins if coin != ZERO_ADDRESS]


@ttl_cache(ttl=600)
def get_price(token, block=None):
    coins = get_underlying_coins(token)
    try:
        coin = (set(coins) & BASIC_TOKENS).pop()
    except KeyError:
        coin = coins[0]

    # there is a registry.get_virtual_price_from_lp_token,
    # but we call pool in case the registry was not deployed at the block
    pool = Contract(get_pool(token))
    virtual_price = pool.get_virtual_price(block_identifier=block) / 1e18
    return [virtual_price, coin]
