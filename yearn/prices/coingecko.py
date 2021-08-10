import requests
from cachetools.func import ttl_cache


@ttl_cache(ttl=600)
def get_price(asset, block=None):
    if block is None:
        params = {'contract_addresses': asset, 'vs_currencies': 'usd'}
        r = requests.get("https://api.coingecko.com/api/v3/simple/token_price/ethereum", params)
        if r.status_code != 200:
            return None
        data = r.json()
        return data[asset.lower()]["usd"]
    else:
        # Coingecko only returns current prices.
        return None
