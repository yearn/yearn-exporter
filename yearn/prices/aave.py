from yearn.utils import contract
from yearn.multicall2 import fetch_multicall
from cachetools.func import ttl_cache

address_provider = contract('0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5')
lending_pool = contract(address_provider.getLendingPool())


@ttl_cache(ttl=3600)
def get_aave_markets():
    tokens = lending_pool.getReservesList()
    markets = fetch_multicall(
        *[[lending_pool, 'getReserveData', token] for token in tokens]
    )
    return {market['aTokenAddress']: token for token, market in zip(tokens, markets)}


def atoken_underlying(token):
    markets = get_aave_markets()
    return markets.get(token)
