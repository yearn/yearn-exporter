from bisect import bisect_left

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

    if len(harvests) < 10:
        raise ApyError("v2:harvests", "harvests are < 10")

    now = harvests[-1]
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

    # Default to higher sample as the result is largely dependent on number of harvests (usually one week sample is sufficient)
    net_apy = max(month_ago_apy, week_ago_apy)

    # performance fee is doubled since 1x strategists + 1x treasury
    performance = (contract.performanceFee() * 2) if hasattr(contract, "performanceFee") else 0
    management = contract.managementFee() if hasattr(contract, "managementFee") else 0

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance/1e4) + management/1e4
    
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

    # Default to higher sample as the result is largely dependent on number of harvests (usually one week sample is sufficient)
    net_apy = max(month_ago_apy, week_ago_apy)

    # performance fee is doubled since 1x strategists + 1x treasury
    performance = (contract.performanceFee() * 2) if hasattr(contract, "performanceFee") else 0
    management = contract.managementFee() if hasattr(contract, "managementFee") else 0

    performance /= 1e4
    management /= 1e4

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance) + management
    
    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    fees = ApyFees(performance=performance, management=management)
    return Apy("v2:averaged", gross_apr, net_apy, fees, points=points)
