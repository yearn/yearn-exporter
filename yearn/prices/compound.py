from brownie import Contract, interface
from cachetools.func import ttl_cache
from yearn.multicall2 import fetch_multicall


@ttl_cache(ttl=3600)
def get_markets():
    comptroller = Contract("0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B")
    creamtroller = Contract('0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258')
    ironbankroller = Contract("0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB")
    
    results = fetch_multicall(
        [comptroller, 'getAllMarkets'],
        [creamtroller, 'getAllMarkets'],
        [ironbankroller, 'getAllMarkets'],
    )
    names = ['compound', 'cream', 'ironbank']
    return dict(zip(names, results))


def is_compound_market(token):
    markets = get_markets()
    return any(token in market for market in markets.values())


def get_price(token, block=None):
    token = Contract(token)
    underlying, exchange_rate, decimals = fetch_multicall(
        [token, 'underlying'],
        [token, 'exchangeRateCurrent'],
        [token, 'decimals'],
        block=block
    )
    exchange_rate /= 1e18
    under_decimals = Contract(underlying).decimals()
    return [exchange_rate * 10 ** (decimals - under_decimals), underlying]
