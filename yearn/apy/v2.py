import logging
import os
from bisect import bisect_left
from datetime import datetime, timedelta
from pprint import pformat

from brownie import chain
from semantic_version.base import Version
from y.networks import Network

from yearn.apy.common import (Apy, ApyBlocks, ApyError, ApyFees, ApyPoints,
                              ApySamples, SharePricePoint, calculate_roi)
from yearn.apy.staking_rewards import get_staking_rewards_apr
from yearn.debug import Debug
from yearn.utils import run_in_thread

logger = logging.getLogger(__name__)

def closest(haystack, needle):
    pos = bisect_left(sorted(haystack), needle)
    if pos == 0:
        return haystack[0]
    if pos == len(haystack):
        return haystack[-1]
    before = haystack[pos - 1]
    after = haystack[pos]
    if after - needle < needle - before:
        return after
    else:
        return before


async def simple(vault, samples: ApySamples) -> Apy:
    harvests = sorted([harvest for strategy in await vault.strategies for harvest in await run_in_thread(getattr, strategy, "harvests")])

    # we don't want to display APYs when vaults are ramping up
    if len(harvests) < 2:
        raise ApyError("v2:harvests", "harvests are < 2")
    
    # set our time values for simple calcs, closest to a harvest around that time period
    now = closest(harvests, samples.now)
    week_ago = closest(harvests, samples.week_ago)
    month_ago = closest(harvests, samples.month_ago)
    
    # set our parameters
    contract = vault.vault
    price_per_share = contract.pricePerShare.coroutine
    
    # calculate our current price
    now_price = await price_per_share(block_identifier=now)

    # get our inception data
    # the first report is when the vault first allocates funds to farm with
    reports = await run_in_thread(getattr, vault, 'reports')
    inception_block = reports[0].block_number
    inception_price = await price_per_share(block_identifier=inception_block)

    if now_price == inception_price:
        raise ApyError("v2:inception", "no change from inception price")
    
    # check our historical data
    if samples.week_ago > inception_block:
        week_ago_price = await price_per_share(block_identifier=week_ago)
    else:
        week_ago_price = inception_price

    if samples.month_ago > inception_block:
        month_ago_price = await price_per_share(block_identifier=month_ago)
    else:
        month_ago_price = inception_price

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)
    month_ago_point = SharePricePoint(samples.month_ago, month_ago_price)
    inception_point = SharePricePoint(inception_block, inception_price)

    week_ago_apy = calculate_roi(now_point, week_ago_point)
    month_ago_apy = calculate_roi(now_point, month_ago_point)
    inception_apy = calculate_roi(now_point, inception_point)

    # use the first non-zero apy, ordered by precedence
    # For everything that isn't ETH, prioritize the weekly APY over the monthly. 
    # APYs on other networks are vary quickly and harvests are more frequent than on mainnet, 
    # where infrequent harvests mean showing the weekly APY results in misleading spikes
    if chain.id != Network.Mainnet:
        apys = [week_ago_apy, month_ago_apy, inception_apy]
    else:
        apys = [month_ago_apy, week_ago_apy, inception_apy]

    net_apy = next((value for value in apys if value != 0), 0)

    # for performance fee, half comes from strategy (strategist share) and half from the vault (treasury share)
    strategy_fees = []
    for strategy in await vault.strategies: # look at all of our strategies
        strategy_info = await contract.strategies.coroutine(strategy.strategy)
        debt_ratio = strategy_info['debtRatio'] / 10000
        performance_fee = strategy_info['performanceFee']
        proportional_fee = debt_ratio * performance_fee
        strategy_fees.append(proportional_fee)
    
    strategy_performance = sum(strategy_fees)
    vault_performance = await contract.performanceFee.coroutine() if hasattr(contract, "performanceFee") else 0
    management = await contract.managementFee.coroutine() if hasattr(contract, "managementFee") else 0
    performance = vault_performance + strategy_performance

    performance /= 1e4
    management /= 1e4

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance) + management

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault.api_version) >= Version("0.3.5"):
        net_apy = 0

    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    blocks = ApyBlocks(samples.now, samples.week_ago, samples.month_ago, inception_block)
    fees = ApyFees(performance=performance, management=management)
    return Apy("v2:simple", gross_apr, net_apy, fees, points=points, blocks=blocks)


async def average(vault, samples: ApySamples) -> Apy:
    reports = await run_in_thread(getattr, vault, "reports")

    # we don't want to display APYs when vaults are ramping up
    if len(reports) < 2:
        raise ApyError("v2:reports", "reports are < 2")
    
    # set our parameters
    contract = vault.vault
    price_per_share = contract.pricePerShare.coroutine
    # calculate our current price
    now_price = await price_per_share(block_identifier=samples.now)

    # get our inception data
    # the first report is when the vault first allocates funds to farm with
    inception_block = reports[0].block_number
    inception_price = await price_per_share(block_identifier=inception_block)

    if now_price == inception_price:
        raise ApyError("v2:inception", "no change from inception price")
    
    now_point = SharePricePoint(samples.now, now_price)
    inception_point = SharePricePoint(inception_block, inception_price)

    # check our historical data
    if samples.week_ago > inception_block:
        week_ago_price = await price_per_share(block_identifier=samples.week_ago)
        week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)
    else:
        week_ago_price = inception_price
        week_ago_point = inception_point

    if samples.month_ago > inception_block:
        month_ago_price = await price_per_share(block_identifier=samples.month_ago)
        month_ago_point = SharePricePoint(samples.month_ago, month_ago_price)
    else:
        month_ago_price = inception_price
        month_ago_point = inception_point

    week_ago_apy = calculate_roi(now_point, week_ago_point)
    month_ago_apy = calculate_roi(now_point, month_ago_point)
    inception_apy = calculate_roi(now_point, inception_point)
    
    # we should look at a vault's harvests, age, etc to determine whether to show new APY or not

    # use the first non-zero apy, ordered by precedence
    # For everything that isn't ETH, prioritize the weekly APY over the monthly. 
    # APYs on other networks are vary quickly and harvests are more frequent than on mainnet, 
    # where infrequent harvests mean showing the weekly APY results in misleading spikes
    if chain.id != Network.Mainnet:
        apys = [week_ago_apy, month_ago_apy]
    else:
        apys = [month_ago_apy, week_ago_apy]

    two_months_ago = datetime.now() - timedelta(days=60)
    if await contract.activation.coroutine() > two_months_ago.timestamp():
        # if the vault was activated less than two months ago then it's ok to use
        # the inception apy, otherwise using it isn't representative of the current apy
        apys.append(inception_apy)

    net_apy = next((value for value in apys if value != 0), 0)

    # for performance fee, half comes from strategy (strategist share) and half from the vault (treasury share)
    strategy_fees = []
    for strategy in await vault.strategies: # look at all of our strategies
        strategy_info = await contract.strategies.coroutine(strategy.strategy)
        debt_ratio = strategy_info['debtRatio'] / 10000
        performance_fee = strategy_info['performanceFee']
        proportional_fee = debt_ratio * performance_fee
        strategy_fees.append(proportional_fee)
    
    strategy_performance = sum(strategy_fees)
    vault_performance = await contract.performanceFee.coroutine() if hasattr(contract, "performanceFee") else 0
    management = await contract.managementFee.coroutine() if hasattr(contract, "managementFee") else 0
    performance = vault_performance + strategy_performance

    performance /= 1e4
    management /= 1e4

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    # if net_apy is negative no fees are charged
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding if net_apy > 0 else net_apy

    # calculate our pre-fee APR
    performance_fee_denominator = 1 - performance 
    if performance_fee_denominator == 0:
        gross_apr = apr_after_fees + management
    else: 
        gross_apr = apr_after_fees / performance_fee_denominator + management

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault.api_version) >= Version("0.3.5"):
        net_apy = 0

    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    blocks = ApyBlocks(samples.now, samples.week_ago, samples.month_ago, inception_block)
    fees = ApyFees(performance=performance, management=management)
    staking_rewards_apr = await get_staking_rewards_apr(vault, samples)
    if os.getenv("DEBUG", None):
        logger.info(pformat(Debug().collect_variables(locals())))
    return Apy("v2:averaged", gross_apr, net_apy, fees, points=points, blocks=blocks, staking_rewards_apr=staking_rewards_apr)
