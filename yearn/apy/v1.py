from yearn.utils import contract_creation_block

from yearn.apy.common import (
    Apy,
    ApyError,
    ApyPoints,
    ApyFees,
    ApySamples,
    SharePricePoint,
    calculate_roi,
)


def simple(vault, samples: ApySamples) -> Apy:
    inception_block = contract_creation_block(vault.vault.address)

    if not inception_block:
        raise ApyError("v1:blocks", "inception_block not found")

    contract = vault.vault
    price_per_share = contract.getPricePerFullShare

    inception_price = 1e18

    try:
        now_price = price_per_share(block_identifier=samples.now)
    except ValueError:
        now_price = inception_price

    if samples.week_ago > inception_block:
        try:
            week_ago_price = price_per_share(block_identifier=samples.week_ago)
        except ValueError:
            week_ago_price = now_price
    else:
        week_ago_price = now_price

    if samples.month_ago > inception_block:
        try:
            month_ago_price = price_per_share(block_identifier=samples.month_ago)
        except ValueError:
            month_ago_price = week_ago_price
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
    apys = [month_ago_apy, week_ago_apy, inception_apy] 
    net_apy = next((value for value in apys if value != 0), 0)

    strategy = vault.strategy
    withdrawal = strategy.withdrawalFee() if hasattr(strategy, "withdrawalFee") else 0
    strategist_performance = strategy.performanceFee() if hasattr(strategy, "performanceFee") else 0
    strategist_reward = strategy.strategistReward() if hasattr(strategy, "strategistReward") else 0
    treasury = strategy.treasuryFee() if hasattr(strategy, "treasuryFee") else 0

    performance = (strategist_reward + strategist_performance + treasury) / 1e4

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    # if net_apy is negative no fees are charged
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding if net_apy > 0 else net_apy

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance)
    
    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    fees = ApyFees(performance=performance, withdrawal=withdrawal)
    return Apy("v1:simple", gross_apr, net_apy, fees, points=points)
