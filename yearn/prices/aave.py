from brownie import multicall
from yearn.utils import contract
from cachetools.func import ttl_cache

address_provider = contract('0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5')
lending_pool = contract(address_provider.getLendingPool())


@ttl_cache(ttl=3600)
def get_aave_markets():
    with multicall:
        markets = {
            token: lending_pool.getReserveData(token)
            for token in lending_pool.getReservesList()
        }
    return {markets[token]['aTokenAddress']: token for token in markets}


def atoken_underlying(token):
    markets = get_aave_markets()
    return markets.get(token)
