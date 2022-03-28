import logging
from typing import Optional

from brownie import chain
from cachetools.func import ttl_cache

from yearn.exceptions import PriceError
from yearn.networks import Network
from yearn.prices import balancer as bal
from yearn.prices import constants, curve
from yearn.prices.aave import aave
from yearn.prices.band import band
from yearn.prices.chainlink import chainlink
from yearn.prices.compound import compound
from yearn.prices.fixed_forex import fixed_forex
from yearn.prices.generic_amm import generic_amm
from yearn.prices.incidents import INCIDENTS
from yearn.prices.synthetix import synthetix
from yearn.prices.uniswap.v1 import uniswap_v1
from yearn.prices.uniswap.v2 import uniswap_v2
from yearn.prices.uniswap.v3 import uniswap_v3
from yearn.prices.yearn import yearn_lens
from yearn.special import Backscratcher
from yearn.typing import Address, AddressOrContract, AddressString, Block
from yearn.utils import contract

logger = logging.getLogger(__name__)

@ttl_cache(10000)
def get_price(
    token: AddressOrContract,
    block: Optional[Block] = None,
    return_price_during_vault_downtime: bool = False
    ) -> float:

    token = unwrap_token(token)
    return find_price(token, block, return_price_during_vault_downtime=return_price_during_vault_downtime)

def unwrap_token(token: AddressOrContract) -> AddressString:
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
        if aave and token in aave:
            token = aave.atoken_underlying(token)
            logger.debug("aave -> %s", token)

    return token


def find_price(
    token: Address,
    block: Optional[Block],
    return_price_during_vault_downtime: bool = False
    ) -> float:

    price = None
    if token in constants.stablecoins:
        logger.debug("stablecoin -> %s", 1)
        return 1

    elif uniswap_v2 and uniswap_v2.is_uniswap_pool(token):
        price = uniswap_v2.lp_price(token, block=block)
        logger.debug("uniswap pool -> %s", price)

    elif bal.balancer and bal.balancer.is_balancer_pool(token):
        price = bal.balancer.get_price(token, block=block)
        logger.debug("balancer pool -> %s", price)

    elif yearn_lens and yearn_lens.is_yearn_vault(token):
        price = yearn_lens.get_price(token, block=block)
        logger.debug("yearn -> %s", price)

    # token-specific overrides
    if chain.id == Network.Fantom:
        # xcredit
        if token == '0xd9e28749e80D867d5d14217416BFf0e668C10645':
            logger.debug('xcredit -> unwrap')
            wrapper = contract(token)
            price = get_price(wrapper.token(), block=block) * wrapper.getShareValue(block_identifier=block) / 1e18

    elif chain.id == Network.Mainnet:
        # no liquid market for yveCRV-DAO -> return CRV token price
        if token == Backscratcher().vault.address and block and block < 11786563:
            if curve.curve and curve.curve.crv:
                return get_price(curve.curve.crv, block=block)

    markets = [
        chainlink,
        curve.curve,
        compound,
        fixed_forex,
        generic_amm,
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

        if token in market:
            price = market.get_price(token, block=block)

        logger.debug("%s -> %s", market_name, price)

    if isinstance(price, list):
        price, underlying = price
        logger.debug("peel %s %s", price, underlying)
        return price * get_price(underlying, block=block)

    if price is None and return_price_during_vault_downtime:
        for incident in INCIDENTS[token]:
            if incident['start'] <= block <= incident['end']:
                return incident['result']

    if price is None:
        logger.error(f"failed to get price for {_describe_err(token, block)}")
        raise PriceError(f'could not fetch price for {_describe_err(token, block)}')

    return price


def _describe_err(token: Address, block: Optional[Block]) -> str:
    '''
    Assembles a string used to provide as much useful information as possible in PriceError messages
    '''
    try:
        symbol = contract(token).symbol()
    except AttributeError:
        symbol = None

    if block is None:
        if symbol:
            return f"{symbol} {token} on {Network(chain.id).name}"

        return f"malformed token {token} on {Network(chain.id).name}"

    if symbol:
        return f"{symbol} {token} on {Network(chain.id).name} at {block}"

    return f"malformed token {token} on {Network(chain.id).name} at {block}"
