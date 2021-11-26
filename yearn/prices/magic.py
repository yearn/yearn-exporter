import logging

from cachetools.func import ttl_cache

from brownie import chain

from yearn.prices import constants, uniswap

if chain.id == 1:
    from yearn.prices import (
        aave,
        balancer,
        chainlink,
        compound,
        curve,
        fixed_forex,
        synthetix,
        uniswap_v3,
        yearn,
    )
elif chain.id == 250:
    from yearn.prices.band import band

logger = logging.getLogger(__name__)


class PriceError(Exception):
    pass


@ttl_cache(10000)
def get_price(token, block=None):
    token = str(token)
    logger.debug("unwrapping %s", token)

    if token in constants.stablecoins:
        logger.debug("stablecoin -> %s", 1)
        return 1

    if token in constants.ONE_TO_ONE_MAPPING:
        token = constants.ONE_TO_ONE_MAPPING[token]
        logger.debug("one to one -> %s", )

    if chain.id == 1:
        return get_price_eth(token, block)
    elif chain.id == 250:
        return get_price_ftm(token, block)


def get_price_ftm(token, block=None):
    price = None

    if not price:
        price = band.get_price(token, block=block)
        logger.debug("band -> %s", price)

    if not price:
        price = uniswap.get_price(token, router="default", block=block)
        logger.debug("uniswap v2 -> %s", price)

    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token} at {block}')

    return price


def get_price_eth(token, block=None):
    price = None

    if token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        token = constants.weth

    if token in aave.aave:
        token = aave.aave.atoken_underlying(token)
        logger.debug("aave -> %s", token)

    # we can exit early with known tokens
    if token in chainlink.chainlink:
        price = chainlink.get_price(token, block=block)
        logger.debug("chainlink -> %s", price)

    elif yearn.is_yearn_vault(token):
        price = yearn.get_price(token, block=block)
        logger.debug("yearn -> %s", price)

    elif curve.curve.get_pool(token):
        price = curve.curve.get_price(token, block=block)
        logger.debug("curve lp -> %s", price)

    elif compound.is_compound_market(token):
        price = compound.get_price(token, block=block)
        logger.debug("compound -> %s", price)

    elif fixed_forex.is_fixed_forex(token):
        price = fixed_forex.get_price(token, block=block)
        logger.debug("fixed forex -> %s", price)

    elif synthetix.is_synth(token):
        price = synthetix.get_price(token, block=block)
        logger.debug("synthetix -> %s", price)

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

    # a few more attempts to fetch a price
    if not price:
        price = uniswap.get_price(token, router="sushiswap", block=block)
        logger.debug("sushiswap -> %s", price)
    if not price:
        price = uniswap_v3.get_price(token, block=block)
        logger.debug("uniswap v3 -> %s", price)
    if not price:
        price = uniswap.get_price(token, router="uniswap", block=block)
        logger.debug("uniswap v2 -> %s", price)
    if not price:
        price = uniswap.get_price_v1(token, block=block)
        logger.debug("uniswap v1 -> %s", price)
    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token} at {block}')

    return price
