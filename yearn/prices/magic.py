import logging

from brownie import chain
from cachetools.func import ttl_cache
from yearn.exceptions import PriceError
from yearn.networks import Network
from yearn.prices.aave import aave
from yearn.prices.band import band
from yearn.prices.chainlink import chainlink
from yearn.prices.compound import compound
from yearn.prices.balancer import balancer
from yearn.prices.fixed_forex import fixed_forex
from yearn.prices.synthetix import synthetix
from yearn.prices.uniswap.v1 import uniswap_v1
from yearn.prices.uniswap.v2 import uniswap_v2
from yearn.prices.uniswap.v3 import uniswap_v3
from yearn.prices.yearn import yearn_lens
from yearn.utils import contract

from yearn.prices import constants, curve

logger = logging.getLogger(__name__)

@ttl_cache(10000)
def get_price(token, block=None):
    token = unwrap_token(token)
    return find_price(token, block)


def unwrap_token(token):
    token = str(token)
    logger.debug("unwrapping %s", token)

    if chain.id == Network.Mainnet:
        if token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            return constants.weth
        elif token == "0x4da27a545c0c5B758a6BA100e3a049001de870f5":
            return "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9"  # stkAAVE -> AAVE
        elif token == "0x27D22A7648e955E510a40bDb058333E9190d12D4":
            return "0x0cec1a9154ff802e7934fc916ed7ca50bde6844e"  # PPOOL -> POOL

    if chain.id in [ Network.Mainnet, Network.Fantom ]:
        if token in aave and aave:
            token = aave.atoken_underlying(token)
            logger.debug("aave -> %s", token)

    return token


def find_price(token, block):
    price = None

    if token in constants.stablecoins:
        logger.debug("stablecoin -> %s", 1)
        return 1

    # xcredit
    if chain.id == Network.Fantom and token == '0xd9e28749e80D867d5d14217416BFf0e668C10645':
        logger.debug('xcredit -> unwrap')
        wrapper = contract(token)
        price = get_price(wrapper.token(), block=block) * wrapper.getShareValue() / 1e18

    markets = [
        balancer,
        yearn_lens,
        chainlink,
        curve.curve,
        compound,
        fixed_forex,
        synthetix,
        band,
        uniswap_v2,
        uniswap_v3,
        uniswap_v1
    ]
    for market in markets:
        if price:
            break
        if not market:
            continue

        market_name = market.__class__.__name__
        logger.debug("getting price for token %s with market %s", token, market_name)

        if hasattr(market, 'is_in_pool') and market.is_in_pool(token):
            price = market.get_pool_price(token, block=block)
        if not price and token in market:
            price = market.get_price(token, block=block)

        logger.debug("%s -> %s", market_name, price)

    if isinstance(price, list):
        price, underlying = price
        logger.debug("peel %s %s", price, underlying)
        return price * get_price(underlying, block=block)

    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token} at {block}')

    return price
