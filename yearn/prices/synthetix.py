from brownie import multicall
from cachetools.func import lru_cache, ttl_cache
from eth_abi import encode_single

from yearn.utils import contract


@lru_cache(maxsize=None)
def get_address(name):
    """
    Get contract from Synthetix registry.
    See also https://docs.synthetix.io/addresses/
    """
    address_resolver = contract('0x823bE81bbF96BEc0e25CA13170F5AaCb5B79ba83')
    address = address_resolver.getAddress(encode_single('bytes32', name.encode()))
    proxy = contract(address)
    return contract(proxy.target()) if hasattr(proxy, 'target') else proxy


@ttl_cache(ttl=3600)
def get_synths():
    """
    Get target addresses of all synths.
    """
    proxy_erc20 = get_address('ProxyERC20')
    with multicall:
        synths = [
            proxy_erc20.availableSynths(i)
            for i in range(int(proxy_erc20.availableSynthCount()))
        ]
    return synths


@ttl_cache(ttl=3600)
def is_synth(token):
    """
    Check if a token is a synth.
    """
    synths = get_synths()
    token = contract(token)
    if not hasattr(token, 'target'):
        return False
    target = token.target()
    if target in synths and contract(target).proxy() == token:
        return True
    return False


@lru_cache(maxsize=None)
def get_currency_key(token):
    target = contract(token).target()
    return contract(target).currencyKey()


@ttl_cache(ttl=600)
def get_price(token, block=None):
    """
    Get a price of a synth in dollars.
    """
    exchnage_rates = get_address('ExchangeRates')
    currency_key = get_currency_key(token)
    return exchnage_rates.rateForCurrency(currency_key, block_identifier=block) / 1e18
