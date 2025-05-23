import logging
from decimal import Decimal
from typing import Optional

from brownie import chain
from cachetools.func import ttl_cache
from y import magic
from y.constants import CHAINID
from y.datatypes import AnyAddressType
from y.exceptions import PriceError
from y.networks import Network

from yearn.constants import CRV
from yearn.prices import constants
from yearn.prices.aave import aave
from yearn.prices.balancer import balancer as bal
from yearn.prices.band import band
from yearn.prices.compound import compound
from yearn.prices.fixed_forex import fixed_forex
from yearn.prices.generic_amm import generic_amm
from yearn.prices.incidents import INCIDENTS
from yearn.prices.uniswap.uniswap import uniswaps
from yearn.prices.uniswap.v2 import uniswap_v2
from yearn.prices.yearn import yearn_lens
from yearn.typing import Address, AddressOrContract, AddressString, Block
from yearn.utils import contract

logger = logging.getLogger(__name__)

async def _get_price(token: AnyAddressType, block: Optional[Block]) -> Decimal:
    """ Performs some checks before deferring to ypricemagic. """ 

    if CHAINID == Network.Mainnet:
        # fixes circular import
        from yearn.special import Backscratcher

        # no liquid market for yveCRV-DAO -> return CRV token price
        if token == Backscratcher().vault.address and block < 11786563:
            return Decimal(await _get_price("0xD533a949740bb3306d119CC777fa900bA034cd52", block))
        # no liquidity for curve pool (yvecrv-f) -> return 0
        elif token == "0x7E46fd8a30869aa9ed55af031067Df666EfE87da" and block < 14987514:
            return Decimal(0)
        # no continuous price data before 2020-10-10
        elif token == "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D" and block < 11024342:
            return Decimal(0)
    try:
        return Decimal(await magic.get_price(token, block, sync=False))
    except:
        for incident in INCIDENTS[token]:
            if incident['start'] <= block <= incident['end']:
                return Decimal(incident['result'])
        raise

# Will delete once we're sure we don't need anymore
def get_price(
    token: AddressOrContract,
    block: Optional[Block] = None,
    return_price_during_vault_downtime: bool = False
    ) -> float:

    token = unwrap_token(token)
    block = chain.height if block is None else block
    return find_price(token, block, return_price_during_vault_downtime=return_price_during_vault_downtime)

def unwrap_token(token: AddressOrContract) -> AddressString:
    token = str(token)
    logger.debug("unwrapping %s", token)

    if token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return constants.weth

    if CHAINID == Network.Mainnet:
        if token == "0x4da27a545c0c5B758a6BA100e3a049001de870f5":
            return "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9"  # stkAAVE -> AAVE
        elif token == "0x27D22A7648e955E510a40bDb058333E9190d12D4":
            return "0x0cec1a9154ff802e7934fc916ed7ca50bde6844e"  # PPOOL -> POOL

    if CHAINID in [ Network.Mainnet, Network.Fantom ]:
        if aave:
            asset = contract(token)
            # wrapped aDAI -> aDAI
            if "ATOKEN" in asset.__dict__:
                token = asset.ATOKEN()

            if token in aave:
                token = aave.atoken_underlying(token)
                logger.debug("aave -> %s", token)

    return token

@ttl_cache(10000)
def find_price(
    token: Address,
    block: Block,
    return_price_during_vault_downtime: bool = False
    ) -> float:
    assert block is not None, "You must pass a valid block number as this function is cached."
    price = None
    if token in constants.stablecoins:
        # TODO Code better handling for stablecoin pricing
        logger.debug("stablecoin -> %s", 1)
        return 1

    elif uniswap_v2 and uniswap_v2.is_uniswap_pool(token):
        price = uniswap_v2.lp_price(token, block=block)
        logger.debug("uniswap pool -> %s", price)

    elif bal.selector.get_balancer_for_pool(token):
        bal_for_pool = bal.selector.get_balancer_for_pool(token)
        price = bal_for_pool.get_price(token, block=block)
        logger.debug("balancer %s pool -> %s", bal_for_pool.get_version(), price)

    elif yearn_lens and yearn_lens.is_yearn_vault(token):
        price = yearn_lens.get_price(token, block=block)
        logger.debug("yearn -> %s", price)

    # token-specific overrides
    if CHAINID == Network.Fantom:
        # xcredit
        if token == '0xd9e28749e80D867d5d14217416BFf0e668C10645':
            logger.debug('xcredit -> unwrap')
            wrapper = contract(token)
            price = magic.get_price(wrapper.token(), block=block, sync=False) * wrapper.getShareValue(block_identifier=block) / 1e18

    elif CHAINID == Network.Mainnet:
        # no liquid market for yveCRV-DAO -> return CRV token price
        if token == Backscratcher().vault.address and block < 11786563:
            if CRV:
                return get_price(CRV, block=block)
        # no liquidity for curve pool (yvecrv-f) -> return 0
        elif token == "0x7E46fd8a30869aa9ed55af031067Df666EfE87da" and block < 14987514:
            return 0
        # no continuous price data before 2020-10-10
        elif token == "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D" and block < 11024342:
            return 0

    markets = [
        compound,
        fixed_forex,
        generic_amm,
        band,
        uniswaps
    ]
    for market in markets:
        # break on the first numerical price
        if price or price == 0:
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
                logger.debug("incidents -> %s", price)
                return incident['result']

    if price is None:
        logger.error(f"failed to get price for {_describe_err(token, block)}")
        raise PriceError(f'could not fetch price for {_describe_err(token, block)}')

    if price == 0:
        logger.warning("Price is 0 for token %s at block %d", token, block)

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
            return f"{symbol} {token} on {Network(CHAINID).name}"

        return f"malformed token {token} on {Network(CHAINID).name}"

    if symbol:
        return f"{symbol} {token} on {Network(CHAINID).name} at {block}"

    return f"malformed token {token} on {Network(CHAINID).name} at {block}"
