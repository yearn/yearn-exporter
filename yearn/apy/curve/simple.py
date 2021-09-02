import logging

from brownie import Contract, ZERO_ADDRESS
from semantic_version import Version

from yearn.apy.curve.rewards import rewards

from yearn.prices.curve import curve
from yearn.prices.magic import get_price

from yearn.apy.common import (
    SECONDS_PER_YEAR,
    Apy,
    ApyFees,
    ApyError,
    ApySamples,
    SharePricePoint,
    calculate_roi,
)

logger = logging.getLogger(__name__)

CRV = Contract("0xD533a949740bb3306d119CC777fa900bA034cd52")
CVX = Contract("0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B")

YVECRV_VOTER = "0xF147b8125d2ef93FB6965Db97D6746952a133934"
CONVEX_VOTER = "0x989AEb4d175e16225E39E87d0D97A3360524AD80"

COMPOUNDING = 52
MAX_BOOST = 2.5
PER_MAX_BOOST = 1.0 / MAX_BOOST


def simple(vault, samples: ApySamples) -> Apy:
    lp_token = vault.token.address

    pool_address = curve.get_pool(lp_token)

    gauge_address = curve.get_gauge(pool_address)

    gauge = Contract(gauge_address)
    controller = gauge.controller()
    controller = Contract(controller)

    block = samples.now

    gauge_working_supply = gauge.working_supply(block_identifier=block)
    gauge_weight = controller.gauge_relative_weight.call(gauge_address, block_identifier=block) 

    gauge_inflation_rate = gauge.inflation_rate(block_identifier=block)
    pool = Contract(pool_address)
    pool_price = pool.get_virtual_price(block_identifier=block)

    base_asset_price = get_price(lp_token, block=block) or 1

    crv_price = get_price(CRV, block=block)

    y_working_balance = gauge.working_balances(YVECRV_VOTER, block_identifier=block)
    y_gauge_balance = gauge.balanceOf(YVECRV_VOTER, block_identifier=block)

    base_apr = (
        gauge_inflation_rate
        * gauge_weight
        * (SECONDS_PER_YEAR / gauge_working_supply)
        * (PER_MAX_BOOST / pool_price)
        * crv_price
    ) / base_asset_price

    if y_gauge_balance > 0:
        boost = y_working_balance / (PER_MAX_BOOST * y_gauge_balance) or 1
    else:
        boost = MAX_BOOST

    # FIXME: The HBTC v1 vault is currently still earning yield, but it is no longer boosted.
    if vault.vault.address == "0x46AFc2dfBd1ea0c0760CAD8262A5838e803A37e5":
        boost = 1


    reward_apr = 0
    if hasattr(gauge, "reward_contract"):
        reward_address = gauge.reward_contract()
        if reward_address != ZERO_ADDRESS:
            reward_apr = rewards(reward_address, pool_price, base_asset_price, block=block)
    else:
        reward_apr = 0

    price_per_share = pool.get_virtual_price
    now_price = price_per_share(block_identifier=samples.now)
    try:
        week_ago_price = price_per_share(block_identifier=samples.week_ago)
    except ValueError:
        raise ApyError("crv", "insufficient data")

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)

    pool_apr = calculate_roi(now_point, week_ago_point)
    pool_apy = (((pool_apr / 365) + 1) ** 365) - 1

    # FIXME: crvANKR's pool apy going crazy
    if vault.vault.address == "0xE625F5923303f1CE7A43ACFEFd11fd12f30DbcA4":
        pool_apy = 0

    # prevent circular import for partners calculations
    from yearn.v2.vaults import Vault as VaultV2

    if isinstance(vault, VaultV2):
        contract = vault.vault
        if len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, "keepCRV"):
            crv_keep_crv = vault.strategies[0].strategy.keepCRV(block_identifier=block) / 1e4
        elif len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, "keepCrvPercent"):
            crv_keep_crv = vault.strategies[0].strategy.keepCrvPercent(block_identifier=block) / 1e4
        else:
            crv_keep_crv = 0
        performance = (contract.performanceFee(block_identifier=block) * 2) / 1e4 if hasattr(contract, "performanceFee") else 0
        management = contract.managementFee(block_identifier=block) / 1e4 if hasattr(contract, "managementFee") else 0
    else:
        strategy = vault.strategy
        strategist_performance = strategy.performanceFee(block_identifier=block) if hasattr(strategy, "performanceFee") else 0
        strategist_reward = strategy.strategistReward(block_identifier=block) if hasattr(strategy, "strategistReward") else 0
        treasury = strategy.treasuryFee(block_identifier=block) if hasattr(strategy, "treasuryFee") else 0
        crv_keep_crv = strategy.keepCRV(block_identifier=block) / 1e4 if hasattr(strategy, "keepCRV") else 0

        performance = (strategist_reward + strategist_performance + treasury) / 1e4
        management = 0

    if isinstance(vault, VaultV2) and len(vault.strategies) == 2:
        crv_strategy = vault.strategies[0].strategy
        cvx_strategy = vault.strategies[1].strategy
        cvx_working_balance = gauge.working_balances(CONVEX_VOTER, block_identifier=block)
        cvx_gauge_balance = gauge.balanceOf(CONVEX_VOTER, block_identifier=block)

        if cvx_gauge_balance > 0:
            cvx_boost = cvx_working_balance / (PER_MAX_BOOST * cvx_gauge_balance) or 1
        else:
            cvx_boost = MAX_BOOST
        
        cvx_booster = Contract("0xF403C135812408BFbE8713b5A23a04b3D48AAE31")
        cvx_lock_incentive = cvx_booster.lockIncentive(block_identifier=block)
        cvx_staker_incentive = cvx_booster.stakerIncentive(block_identifier=block)
        cvx_earmark_incentive = cvx_booster.earmarkIncentive(block_identifier=block)
        cvx_fee = (cvx_lock_incentive + cvx_staker_incentive + cvx_earmark_incentive) / 1e4
        cvx_keep_crv = cvx_strategy.keepCRV(block_identifier=block) / 1e4

        total_cliff = 1e3
        max_supply = 1e2 * 1e6 * 1e18 # ?
        reduction_per_cliff = 1e23
        supply = CVX.totalSupply(block_identifier=block)
        cliff = supply / reduction_per_cliff
        if supply <= max_supply:
            reduction = total_cliff - cliff
            cvx_minted_as_crv = reduction / total_cliff
            cvx_price = get_price(CVX, block=block)
            converted_cvx = cvx_price / crv_price
            cvx_printed_as_crv = cvx_minted_as_crv * converted_cvx
        else:
            cvx_printed_as_crv = 0

        cvx_apr = ((1 - cvx_fee) * cvx_boost * base_apr) * (1 + cvx_printed_as_crv) + reward_apr
        cvx_apr_minus_keep_crv = ((1 - cvx_fee) * cvx_boost * base_apr) * ((1 - cvx_keep_crv) + cvx_printed_as_crv)
        
        crv_debt_ratio = vault.vault.strategies(crv_strategy)[2] / 1e4
        cvx_debt_ratio = vault.vault.strategies(cvx_strategy)[2] / 1e4
    else:
        cvx_apr = 0
        cvx_apr_minus_keep_crv = 0
        cvx_keep_crv = 0
        crv_debt_ratio = 1
        cvx_debt_ratio = 0

    crv_apr = base_apr * boost + reward_apr
    crv_apr_minus_keep_crv = base_apr * boost * (1 - crv_keep_crv)

    gross_apr = (1 + (crv_apr * crv_debt_ratio + cvx_apr * cvx_debt_ratio)) * (1 + pool_apy) - 1

    cvx_net_apr = (cvx_apr_minus_keep_crv + reward_apr) * (1 - performance) - management
    cvx_net_farmed_apy = (1 + (cvx_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    cvx_net_apy = ((1 + cvx_net_farmed_apy) * (1 + pool_apy)) - 1

    crv_net_apr = (crv_apr_minus_keep_crv + reward_apr) * (1 - performance) - management
    crv_net_farmed_apy = (1 + (crv_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    crv_net_apy = ((1 + crv_net_farmed_apy) * (1 + pool_apy)) - 1

    net_apy = crv_net_apy * crv_debt_ratio + cvx_net_apy * cvx_debt_ratio

    # 0.3.5+ should never be < 0% because of management
    if isinstance(vault, VaultV2) and net_apy < 0 and Version(vault.api_version) >= Version("0.3.5"):
        net_apy = 0

    fees = ApyFees(performance=performance, management=management, keep_crv=crv_keep_crv, cvx_keep_crv=cvx_keep_crv)
    composite = {
        "boost": boost,
        "pool_apy": pool_apy,
        "boosted_apr": crv_apr,
        "base_apr": base_apr,
        "cvx_apr": cvx_apr,
        "rewards_apr": reward_apr,
    }

    return Apy("crv", gross_apr, net_apy, fees, composite=composite)
