from bisect import bisect_left

from semantic_version.base import Version

from yearn.apy.common import (
    Apy,
    ApyError,
    ApyPoints,
    ApyFees,
    ApySamples,
    SharePricePoint,
    calculate_roi,
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

    if len(harvests) < 4:
        raise ApyError("v2:harvests", "harvests are < 4")

    now = closest(harvests, samples.now)
    week_ago = closest(harvests, samples.week_ago)
    month_ago = closest(harvests, samples.month_ago)
    inception_block = harvests[2]

    contract = vault.vault
    price_per_share = contract.pricePerShare

    now_price = price_per_share(block_identifier=now)

    inception_price = 10 ** contract.decimals()

    if samples.week_ago > inception_block:
        week_ago_price = price_per_share(block_identifier=week_ago)
    else:
        week_ago_price = now_price

    if samples.month_ago > inception_block:
        month_ago_price = price_per_share(block_identifier=month_ago)
    else:
        month_ago_price = week_ago_price

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)
    month_ago_point = SharePricePoint(samples.month_ago, month_ago_price)
    inception_point = SharePricePoint(inception_block, inception_price)

    week_ago_apy = calculate_roi(now_point, week_ago_point)
    month_ago_apy = calculate_roi(now_point, month_ago_point)
    inception_apy = calculate_roi(now_point, inception_point)

    # use the first non-zero apy, ordered by precedence
    apys = [week_ago_apy, month_ago_apy, inception_apy]
    net_apy = next((value for value in apys if value != 0), 0)

    # for performance fee, half comes from strategy (strategist share) and half from the vault (treasury share)
    strategy_fees = []
    for x in range(20): # we can have up to 20 strategies
        try:
            strategy_to_check = contract.withdrawalQueue(x)
            print("Strategy to check", strategy_to_check)
        except AttributeError:
            break
        if strategy_to_check == "0x0000000000000000000000000000000000000000":
            print("No more strategies")
            break
        else:
            print("This is our strategy", strategy_to_check)
            debt_ratio = contract.strategies(strategy_to_check)[2] / 10000
            performance_fee = contract.strategies(strategy_to_check)[0]
            proportional_fee = debt_ratio * performance_fee
            strategy_fees.append(proportional_fee)
    
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

    if len(harvests) < 4:
        raise ApyError("v2:harvests", "harvests are < 4")

    inception_block = harvests[2]

    contract = vault.vault
    price_per_share = contract.pricePerShare

    now_price = price_per_share(block_identifier=samples.now)

    inception_price = 10 ** contract.decimals()

    if samples.week_ago > inception_block:
        week_ago_price = price_per_share(block_identifier=samples.week_ago)
    else:
        week_ago_price = now_price

    if samples.month_ago > inception_block:
        month_ago_price = price_per_share(block_identifier=samples.month_ago)
    else:
        month_ago_price = week_ago_price

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)
    month_ago_point = SharePricePoint(samples.month_ago, month_ago_price)
    inception_point = SharePricePoint(inception_block, inception_price)

    week_ago_apy = calculate_roi(now_point, week_ago_point)
    month_ago_apy = calculate_roi(now_point, month_ago_point)
    inception_apy = calculate_roi(now_point, inception_point)

    # use the first non-zero apy, ordered by precedence
    apys = [week_ago_apy, month_ago_apy, inception_apy]
    net_apy = next((value for value in apys if value != 0), 0)

    # for performance fee, half comes from strategy (strategist share) and half from the vault (treasury share)
    strategy_fees = []
    for x in range(20): # we can have up to 20 strategies
        try:
            strategy_to_check = contract.withdrawalQueue(x)
        except AttributeError:
            break
        if strategy_to_check == "0x0000000000000000000000000000000000000000":
            break
        else:
            debt_ratio = contract.strategies(strategy_to_check)[2] / 10000
            performance_fee = contract.strategies(strategy_to_check)[0]
            proportional_fee = debt_ratio * performance_fee
            strategy_fees.append(proportional_fee)
    
    strategy_performance = sum(strategy_fees)
    vault_performance = contract.performanceFee() if hasattr(contract, "performanceFee") else 0
    management = contract.managementFee() if hasattr(contract, "managementFee") else 0
    performance = vault_performance + strategy_performance

    performance /= 1e4
    management /= 1e4

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    # if net_apy is negative no fees are charged
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding if net_apy > 0 else net_apy

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance) + management

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault.api_version) >= Version("0.3.5"):
        net_apy = 0

    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    fees = ApyFees(performance=performance, management=management)
    return Apy("v2:averaged", gross_apr, net_apy, fees, points=points)
