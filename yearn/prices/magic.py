import logging

from cachetools.func import ttl_cache

from yearn.prices import balancer, chainlink, compound, constants, curve, uniswap, coingecko, yearn

logger = logging.getLogger(__name__)


class PriceError(Exception):
    pass


@ttl_cache(10000)
def get_price(token, block=None):
    token = str(token)
    logger.debug("unwrapping %s", token)
    price = None

    if token in constants.STABLECOINS:
        logger.debug("stablecoin -> %s", 1)
        return 1

    if token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        token = str(constants.weth)

    # we can exit early with known tokens
    if token in chainlink.feeds:
        price = chainlink.get_price(token, block=block)
        logger.debug("chainlink -> %s", price)

    elif yearn.is_yearn_vault(token):
        price = yearn.get_price(token, block=block)
        logger.debug("yearn -> %s", price)

    elif curve.is_curve_lp_token(token):
        price = curve.get_price(token, block=block)
        logger.debug("curve lp -> %s", price)

    elif compound.is_compound_market(token):
        price = compound.get_price(token, block=block)
        logger.debug("compound -> %s", price)

    elif uniswap.is_uniswap_pool(token):
        price = uniswap.lp_price(token, block=block)
        logger.debug("uniswap pool -> %s", price)

    elif balancer.is_balancer_pool(token):
        price = balancer.get_price(token, block=block)
        logger.debug("balancer pool -> %s", price)

    # peel a layer from [multiplier, underlying]
    if isinstance(price, list):
        price, underlying = price
        logger.debug("peel %s %s", price, underlying)
        return price * get_price(underlying, block=block)

    # a few more attempts to fetch a price a token
    if not price:
        price = uniswap.get_price(token, router="sushiswap", block=block)
        logger.debug("sushiswap -> %s", price)
    if not price:
        price = uniswap.get_price(token, router="uniswap", block=block)
        logger.debug("uniswap -> %s", price)
    if not price:
        price = uniswap.get_price_v1(token, block=block)
        logger.debug("uniswap v1 -> %s", price)
    if not price:
        price = coingecko.get_price(token, block=block)
        logger.debug("coingecko -> %s", price)
    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token}')

    return price

def get_price_safe(token, block=None):
    price = 0
    try:
        price = get_price(token, block)
    except PriceError:
        pass
    return price
