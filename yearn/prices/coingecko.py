import logging
import requests
from cachetools.func import ttl_cache

logger = logging.getLogger(__name__)

@ttl_cache(ttl=600)
def get_price(asset, block=None):
    if block is not None:
        logger.warning("Fetching a price from coingecko at block height %s but coingecko can only fetch from the latest", block)

    params = {'contract_addresses': asset, 'vs_currencies': 'usd'}
    r = requests.get("https://api.coingecko.com/api/v3/simple/token_price/ethereum", params)
    if r.status_code != 200:
        return None
    data = r.json()
    return data[asset.lower()]["usd"]
