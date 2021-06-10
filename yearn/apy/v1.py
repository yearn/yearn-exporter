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

    net_apy = month_ago_apy

    strategy = vault.strategy
    withdrawal = strategy.withdrawalFee() if hasattr(strategy, "withdrawalFee") else 0
    strategist_performance = strategy.performanceFee() if hasattr(strategy, "performanceFee") else 0
    strategist_reward = strategy.strategistReward() if hasattr(strategy, "strategistReward") else 0
    treasury = strategy.treasuryFee() if hasattr(strategy, "treasuryFee") else 0

    performance = strategist_reward + strategist_performance + treasury

    apy = net_apy / (1 - performance / 1e4)

    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    fees = ApyFees(performance=performance, withdrawal=withdrawal)
    return Apy("v1:simple", apy, net_apy, fees, points=points)
