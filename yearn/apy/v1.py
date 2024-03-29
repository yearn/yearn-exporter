from y.contracts import contract_creation_block_async

from yearn.apy.common import (
    Apy,
    ApyBlocks,
    ApyError,
    ApyPoints,
    ApyFees,
    ApySamples,
    SharePricePoint,
    calculate_roi,
)


async def simple(vault, samples: ApySamples) -> Apy:
    inception_block = await contract_creation_block_async(vault.vault.address)

    if not inception_block:
        raise ApyError("v1:blocks", "inception_block not found")

    contract = vault.vault
    price_per_share = contract.getPricePerFullShare.coroutine

    inception_price = 1e18

    try:
        now_price = await price_per_share(block_identifier=samples.now)
    except ValueError:
        now_price = inception_price

    if samples.week_ago > inception_block:
        try:
            week_ago_price = await price_per_share(block_identifier=samples.week_ago)
        except ValueError:
            week_ago_price = now_price
    else:
        week_ago_price = now_price

    if samples.month_ago > inception_block:
        try:
            month_ago_price = await price_per_share(block_identifier=samples.month_ago)
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
    withdrawal = await strategy.withdrawalFee.coroutine() if hasattr(strategy, "withdrawalFee") else 0
    strategist_performance = await strategy.performanceFee.coroutine() if hasattr(strategy, "performanceFee") else 0
    strategist_reward = await strategy.strategistReward.coroutine() if hasattr(strategy, "strategistReward") else 0
    treasury = await strategy.treasuryFee.coroutine() if hasattr(strategy, "treasuryFee") else 0

    performance = (strategist_reward + strategist_performance + treasury) / 1e4

    # assume we are compounding every week
    compounding = 52

    # calculate our APR after fees
    # if net_apy is negative no fees are charged
    apr_after_fees = compounding * ((net_apy + 1) ** (1 / compounding)) - compounding if net_apy > 0 else net_apy

    # calculate our pre-fee APR
    gross_apr = apr_after_fees / (1 - performance)
    
    points = ApyPoints(week_ago_apy, month_ago_apy, inception_apy)
    blocks = ApyBlocks(samples.now, samples.week_ago, samples.month_ago, inception_block)
    fees = ApyFees(performance=performance, withdrawal=withdrawal)
    return Apy("v1:simple", gross_apr, net_apy, fees, points=points, blocks=blocks)
