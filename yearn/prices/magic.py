import logging

from brownie import chain
from cachetools.func import ttl_cache
from yearn.exceptions import PriceError, UnsupportedNetwork
from yearn.networks import Network
from yearn.prices.aave import aave
from yearn.prices.band import band
from yearn.prices.chainlink import chainlink
from yearn.prices.compound import compound
from yearn.prices.fixed_forex import fixed_forex
from yearn.prices.synthetix import synthetix
from yearn.prices.uniswap.v1 import uniswap_v1
from yearn.prices.uniswap.v2 import uniswap_v2
from yearn.prices.uniswap.v3 import uniswap_v3
from yearn.prices.yearn import yearn_lens
from yearn.utils import contract

from yearn.prices import balancer, constants, curve

logger = logging.getLogger(__name__)



@ttl_cache(10000)
def get_price(token, block=None):
    token = str(token)
    logger.debug("unwrapping %s", token)

    if token in constants.stablecoins:
        logger.debug("stablecoin -> %s", 1)
        return 1

    if chain.id == Network.Mainnet:
        return get_price_eth(token, block)
    elif chain.id == Network.Fantom:
        return get_price_ftm(token, block)
    elif chain.id == Network.Arbitrum:
        return get_price_arbi(token, block)
    else:
        raise UnsupportedNetwork('magic price oracle is not supported on this network')


def get_price_arbi(token, block=None):
    price = None

    if token in compound:
        price = compound.get_price(token, block=block)
        logger.debug("compound -> %s", price)
    
    if isinstance(price, list):
        price, underlying = price
        logger.debug("peel %s %s", price, underlying)
        return price * get_price(underlying, block=block)

    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token} at {block}')

    return price


def get_price_ftm(token, block=None):
    price = None

    if token in aave:
        token = aave.atoken_underlying(token)
        logger.debug("aave -> %s", token)

    if token in compound:
        price = compound.get_price(token, block=block)
        logger.debug("compound -> %s", price)

    elif token in curve.curve:
        price = curve.curve.get_price(token, block=block)
        logger.debug("curve lp -> %s", price)

    if isinstance(price, list):
        price, underlying = price
        logger.debug("peel %s %s", price, underlying)
        return price * get_price(underlying, block=block)

    if not price:
        price = band.get_price(token, block=block)
        logger.debug("band -> %s", price)

    if uniswap_v2.is_uniswap_pool(token):
        price = uniswap_v2.lp_price(token, block=block)
        logger.debug("uniswap pool -> %s", price)

    if not price:
        price = uniswap_v2.get_price(token, block=block)
        logger.debug("uniswap v2 -> %s", price)

    # xcredit
    if token == '0xd9e28749e80D867d5d14217416BFf0e668C10645':
        logger.debug('xcredit -> unwrap')
        wrapper = contract(token)
        return get_price(wrapper.token()) * wrapper.getShareValue() / 1e18

    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token} at {block}')

    return price


def get_price_eth(token, block=None):
    price = None

    if token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        token = constants.weth
    elif token == "0x4da27a545c0c5B758a6BA100e3a049001de870f5":
        token = "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9"  # stkAAVE -> AAVE
    elif token == "0x27D22A7648e955E510a40bDb058333E9190d12D4":
        token = "0x0cec1a9154ff802e7934fc916ed7ca50bde6844e"  # PPOOL -> POOL

    if token in aave:
        token = aave.atoken_underlying(token)
        logger.debug("aave -> %s", token)

    # we can exit early with known tokens
    if token in chainlink:
        price = chainlink.get_price(token, block=block)
        logger.debug("chainlink -> %s", price)

    elif yearn_lens.is_yearn_vault(token):
        price = yearn_lens.get_price(token, block=block)
        logger.debug("yearn -> %s", price)

    elif token in curve.curve:
        price = curve.curve.get_price(token, block=block)
        logger.debug("curve lp -> %s", price)

    elif token in compound:
        price = compound.get_price(token, block=block)
        logger.debug("compound -> %s", price)

    elif token in fixed_forex:
        price = fixed_forex.get_price(token, block=block)
        logger.debug("fixed forex -> %s", price)

    elif token in synthetix:
        price = synthetix.get_price(token, block=block)
        logger.debug("synthetix -> %s", price)

    elif uniswap_v2.is_uniswap_pool(token):
        price = uniswap_v2.lp_price(token, block=block)
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
        price = uniswap_v2.get_price(token, block=block)
        logger.debug("uniswap v2 -> %s", price)
    if not price:
        price = uniswap_v3.get_price(token, block=block)
        logger.debug("uniswap v3 -> %s", price)
    if not price:
        price = uniswap_v1.get_price(token, block=block)
        logger.debug("uniswap v1 -> %s", price)
    if not price:
        logger.error("failed to get price for %s", token)
        raise PriceError(f'could not fetch price for {token} at {block}')

    return price
