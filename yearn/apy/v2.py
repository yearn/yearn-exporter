from bisect import bisect_left
from datetime import datetime, timedelta

from semantic_version.base import Version
from yearn.networks import Network
from brownie import chain
from yearn.prices.curve import curve
from yearn.utils import contract as get_contract
from yearn.apy.common import (
    Apy,
    ApyError,
    ApyPoints,
    ApyFees,
    ApySamples,
    SharePricePoint,
    calculate_roi,
    try_composite as crv_composite
)

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


def simple(vault, samples: ApySamples) -> Apy:
    harvests = sorted([harvest for strategy in vault.strategies for harvest in strategy.harvests])
    print("run our simple v2")

    # we don't want to display APYs when vaults are ramping up
    if len(harvests) < 2:
        raise ApyError("v2:harvests", "harvests are < 2")
    
    # set our time values for simple calcs, closest to a harvest around that time period
    now = closest(harvests, samples.now)
    week_ago = closest(harvests, samples.week_ago)
    month_ago = closest(harvests, samples.month_ago)
    
    # set our parameters
    contract = vault.vault
    price_per_share = contract.pricePerShare
    
    # calculate our current price
    now_price = price_per_share(block_identifier=now)

    # get our inception data
    inception_price = 10 ** contract.decimals()
    inception_block = harvests[:2][-1]

    if now_price == inception_price:
        raise ApyError("v2:inception", "no change from inception price")
    
    # check our historical data
    if samples.week_ago > inception_block:
        week_ago_price = price_per_share(block_identifier=week_ago)
    else:
        week_ago_price = inception_price

    if samples.month_ago > inception_block:
        month_ago_price = price_per_share(block_identifier=month_ago)
    else:
        month_ago_price = inception_price

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)
    month_ago_point = SharePricePoint(samples.month_ago, month_ago_price)
    inception_point = SharePricePoint(inception_block, inception_price)

    week_ago_apy = calculate_roi(now_point, week_ago_point)
    month_ago_apy = calculate_roi(now_point, month_ago_point)
    inception_apy = calculate_roi(now_point, inception_point)

    strategy_fees = []
    now_apy = 0
    
    # generate our average strategy APY and get our fees
    for strategy in vault.strategies:
        total_debt_ratio_allocated = vault.vault.debtRatio()
        if total_debt_ratio_allocated > 0:
            debt_ratio = (contract.strategies(strategy.strategy)['debtRatio'] / total_debt_ratio_allocated)
        else:
            debt_ratio = 0
        strategy_apy = strategy.apy.net_apy
        now_apy += debt_ratio * strategy_apy
        performance_fee = contract.strategies(strategy.strategy)['performanceFee']
        proportional_fee = debt_ratio * performance_fee
        strategy_fees.append(proportional_fee)

    # use the first non-zero apy, ordered by precedence
    apys = [now_apy, week_ago_apy, month_ago_apy, inception_apy]
    net_apy = next((value for value in apys if value != 0), 0)
    
    strategy_performance = sum(strategy_fees)
    vault_performance = contract.performanceFee() if hasattr(contract, "performanceFee") else 0
    management = contract.managementFee() if hasattr(contract, "managementFee") else 0
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
    fees = ApyFees(performance=performance, management=management)
    return Apy("v2:simple", gross_apr, net_apy, fees, points=points)


def average(vault, samples: ApySamples) -> Apy:
    harvests = sorted([harvest for strategy in vault.strategies for harvest in strategy.harvests])
    print("run our average v2")

    # we don't want to display APYs when vaults are ramping up
    if len(harvests) < 2:
        raise ApyError("v2:harvests", "harvests are < 2")
    
    # set our parameters
    contract = vault.vault
    price_per_share = contract.pricePerShare
    
    # calculate our current price
    now_price = price_per_share(block_identifier=samples.now)

    # get our inception data
    inception_price = 10 ** contract.decimals()
    inception_block = harvests[:2][-1]

    if now_price == inception_price:
        raise ApyError("v2:inception", "no change from inception price")
    
    # check our historical data
    if samples.week_ago > inception_block:
        week_ago_price = price_per_share(block_identifier=samples.week_ago)
    else:
        week_ago_price = inception_price

    if samples.month_ago > inception_block:
        month_ago_price = price_per_share(block_identifier=samples.month_ago)
    else:
        month_ago_price = inception_price

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)
    month_ago_point = SharePricePoint(samples.month_ago, month_ago_price)
    inception_point = SharePricePoint(inception_block, inception_price)

    week_ago_apy = calculate_roi(now_point, week_ago_point)
    month_ago_apy = calculate_roi(now_point, month_ago_point)
    inception_apy = calculate_roi(now_point, inception_point)

    strategy_fees = []
    now_apy = 0
    curve_apy = 0
    
    # generate our average strategy APY and get our fees
    for strategy in vault.strategies:
        total_debt_ratio_allocated = vault.vault.debtRatio()
        if total_debt_ratio_allocated > 0:
            debt_ratio = (contract.strategies(strategy.strategy)['debtRatio'] / total_debt_ratio_allocated)
        else:
            debt_ratio = 0
        strategy_apy = strategy.apy.net_apy
        now_apy += debt_ratio * strategy_apy
        performance_fee = contract.strategies(strategy.strategy)['performanceFee']
        proportional_fee = debt_ratio * performance_fee
        strategy_fees.append(proportional_fee)
        
        # for curve vaults, we need more data
        if hasattr(strategy.strategy, "keepCRV") or hasattr(strategy.strategy, "keepCrvPercent"):
            # get price points for our historical pool APY
            lp_token = vault.token.address
            pool_address = curve.get_pool(lp_token)
            print("pool_address", pool_address)
            pool = get_contract(pool_address)         
            print("pool", pool)   
            pool_virtual_price = pool.get_virtual_price
            
            # get our virtual prices at different timepoints
            now_price = pool_virtual_price(block_identifier=samples.now)
            try:
                week_ago_pool_price = pool_virtual_price(block_identifier=samples.week_ago)
            except ValueError:
                week_ago_pool_price = 1e18
            try:
                month_ago_pool_price = pool_virtual_price(block_identifier=samples.month_ago)
            except ValueError:
                month_ago_pool_price = 1e18
            try:
                inception_pool_price = pool_virtual_price(block_identifier=inception_block)
            except ValueError:
                inception_pool_price = 1e18
            
            now_point = SharePricePoint(samples.now, now_price)
            week_ago_point = SharePricePoint(samples.week_ago, week_ago_pool_price)
            month_ago_point = SharePricePoint(samples.month_ago, month_ago_pool_price)
            inception_point = SharePricePoint(inception_block, inception_pool_price)
                        
            # calculate our pool APYs
            pool_apr = calculate_roi(now_point, week_ago_point)
            weekly_pool_apy = (((pool_apr / 365) + 1) ** 365) - 1
            monthly_pool_apr = calculate_roi(now_point, month_ago_point)
            monthly_pool_apy = (((monthly_pool_apr / 365) + 1) ** 365) - 1
            inception_pool_apr = calculate_roi(now_point, inception_point)
            inception_pool_apy = (((inception_pool_apr / 365) + 1) ** 365) - 1
            
            # update our historical apys with pool data
            week_ago_apy = (1+ week_ago_apy) * (1 + weekly_pool_apy) - 1
            month_ago_apy = (1+ month_ago_apy) * (1 + monthly_pool_apy) - 1
            inception_apy = (1+ inception_apy) * (1 + inception_pool_apy) - 1
            
            if crv_composite:
               keep_crv += strategy.apy.fees.keep_crv * debt_ratio
               boost += strategy.apy.strategy_composite["boost"] * debt_ratio
               pool_apy += strategy.apy.strategy_composite["pool_apy"] * debt_ratio
               base_apr += strategy.apy.strategy_composite["base_apr"] * debt_ratio
               boosted_apr += strategy.apy.strategy_composite["boosted_apr"] * debt_ratio
               reward_apr += strategy.apy.strategy_composite["rewards_apr"] * debt_ratio
               cvx_apr += strategy.apy.strategy_composite["cvx_apr"] * debt_ratio
            
    if crv_composite:
        composite = {
            "boost": boost,
            "pool_apy": pool_apy,
            "base_apr": base_apr,
            "boosted_apr": boosted_apr,
            "rewards_apr": reward_apr,
            "cvx_apr": cvx_apr,
        }

    strategy_performance = sum(strategy_fees)
    vault_performance = contract.performanceFee() if hasattr(contract, "performanceFee") else 0
    management = contract.managementFee() if hasattr(contract, "managementFee") else 0
    performance = vault_performance + strategy_performance

    # use the first non-zero apy, ordered by precedence
    apys = [now_apy, week_ago_apy, month_ago_apy, inception_apy]
    two_months_ago = datetime.now() - timedelta(days=60)
    if contract.activation() > two_months_ago.timestamp():
        # if the vault was activated less than two months ago then it's ok to use
        # the inception apy, otherwise using it isn't representative of the current apy
        apys.append(inception_apy)

    net_apy = next((value for value in apys if value != 0), 0)
    
    performance /= 1e4
    management /= 1e4

    # assume we are compounding every week on mainnet, daily on sidechains
    if chain.id == Network.Mainnet:
        compounding = 52
    else:
        compounding = 365.25

    # calculate our APR after fees
    # if net_apy is negative no fees are charged
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding if net_apy > 0 else net_apy

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance) + management

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault.api_version) >= Version("0.3.5"):
        net_apy = 0

    points = ApyPoints(now_apy, week_ago_apy, month_ago_apy, inception_apy)
    fees = ApyFees(performance=performance, management=management)
    if crv_composite:
        return Apy("v2:aggregate", gross_apr, net_apy, fees, points=points, composite=composite)
    else:
        return Apy("v2:aggregate", gross_apr, net_apy, fees, points=points)
