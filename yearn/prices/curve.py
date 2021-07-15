from brownie import ZERO_ADDRESS, Contract
from cachetools.func import ttl_cache
from toolz import take

from yearn.cache import memory
from yearn.multicall2 import fetch_multicall

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

OVERRIDES = {
    '0x53a901d48795C58f485cBB38df08FA96a24669D5': {
        'name': 'reth',
        'pool': '0xF9440930043eb3997fc70e1339dBb11F341de7A8',
        'coins': [
            '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',  # ETH
            '0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593',  # rETH
        ],
    }
}
CRYPTOPOOLS = {
    '0xcA3d75aC011BF5aD07a98d02f18225F9bD9A6BDF': {
        'pool': '0x80466c64868E1ab14a1Ddf27A676C3fcBE638Fe5',
    },
    '0xc4AD29ba4B3c580e6D59105FFf484999997675Ff': {
        'pool': '0xD51a44d3FaE010294C616388b506AcdA1bfAAE46',
    },
}


@memory.cache()
def get_pool(token):
    if token in OVERRIDES:
        return OVERRIDES[token]['pool']
    if token in CRYPTOPOOLS:
        return CRYPTOPOOLS[token]['pool']
    if set(metapool_factory.get_underlying_coins(token)) != {ZERO_ADDRESS}:
        return token
    return curve_registry.get_pool_from_lp_token(token)


@memory.cache()
def is_curve_lp_token(token):
    return get_pool(token) != ZERO_ADDRESS


@memory.cache()
def get_underlying_coins(token):
    if token in OVERRIDES:
        return OVERRIDES[token]['coins']
    pool = get_pool(token)
    coins = curve_registry.get_underlying_coins(pool)
    if set(coins) == {ZERO_ADDRESS}:
        coins = metapool_factory.get_underlying_coins(token)
    return [coin for coin in coins if coin != ZERO_ADDRESS]


def cryptopool_lp_price(token, block=None):
    pool = Contract(CRYPTOPOOLS[token]['pool'])
    token = Contract(token)
    result = fetch_multicall(*[[pool, 'coins', i] for i in range(8)])
    tokens = [Contract(token) for token in result if token]
    n = len(tokens)
    result = iter(
        fetch_multicall(
            [token, 'totalSupply'],
            *[[token, 'decimals'] for token in tokens],
            *[[pool, 'balances', i] for i in range(n)],
            *[[pool, 'price_oracle', i] for i in range(n - 1)],
            block=block
        )
    )
    supply = next(result) / 1e18
    scales = [10 ** decimals for decimals in take(n, result)]
    balances = [balance / scale for balance, scale in zip(take(n, result), scales)]
    # oracles return price with the first coin as a quote currency
    prices = [1] + [price / 1e18 for price in take(n - 1, result)]
    scale = sum(balance * price for balance, price in zip(balances, prices)) / supply
    return [scale, str(tokens[0])]


@ttl_cache(ttl=600)
def get_price(token, block=None):
    if token in CRYPTOPOOLS:
        return cryptopool_lp_price(token, block)

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
