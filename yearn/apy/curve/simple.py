import logging
from typing import Union

from brownie import Contract, interface

from yearn.apy.curve.rewards import rewards

from yearn.v2.registry import Vault as VaultV2
from yearn.vaults_v1 import VaultV1

from yearn.prices.curve import get_pool, get_underlying_coins, curve_registry
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


WBTC = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
BTC_LIKE = [
    WBTC,
    "0xfE18be6b3Bd88A2D2A7f928d00292E7a9963CfC6",  # sBTC
    "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D",  # renBTC
]

WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
ETH_LIKE = [
    WETH,
    "0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb",  # sETH
    "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",  # stETH
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # pure eth
]

CRV = "0xD533a949740bb3306d119CC777fa900bA034cd52"

YVECRV_VOTER = "0xF147b8125d2ef93FB6965Db97D6746952a133934"

COMPOUNDING = 52
MAX_BOOST = 2.5
PER_MAX_BOOST = 1.0 / MAX_BOOST


def simple(vault: Union[VaultV1, VaultV2], samples: ApySamples) -> Apy:
    lp_token = vault.token.address

    pool_address = get_pool(lp_token)
    gauge_addresses = curve_registry.get_gauges(pool_address)

    gauge_address = gauge_addresses[0][0]

    # FIXME: crvUSDP doesn't have a gauge connected in the registry
    if vault.vault.address == "0x1B5eb1173D2Bf770e50F10410C9a96F7a8eB6e75":
        gauge = "0x055be5DDB7A925BfEF3417FC157f53CA77cA7222"

    gauge = interface.CurveGauge(gauge_address)
    controller = gauge.controller()
    controller = interface.CurveGaugeController(controller)

    gauge_working_supply = gauge.working_supply()
    gauge_weight = controller.gauge_relative_weight(gauge_address)

    gauge_inflation_rate = gauge.inflation_rate()
    pool_price = curve_registry.get_virtual_price_from_lp_token(lp_token)

    underlying_coins = get_underlying_coins(lp_token)

    btc_like = any([coin in BTC_LIKE for coin in underlying_coins])
    eth_like = any([coin in ETH_LIKE for coin in underlying_coins])

    base_asset = WBTC if btc_like else WETH if eth_like else underlying_coins[0]
    base_asset_price = get_price(base_asset) or 1

    crv_price = get_price(CRV)

    y_working_balance = gauge.working_balances(YVECRV_VOTER)
    y_gauge_balance = gauge.balanceOf(YVECRV_VOTER)

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

    boosted_apr = base_apr * boost

    try:
        reward_address = gauge.reward_contract()
        assert reward_address != ZERO_ADDRESS
        reward_apr = rewards(reward_address, pool_price, base_asset_price)
    except:
        reward_apr = 0

    price_per_share = curve_registry.get_virtual_price_from_lp_token
    now_price = price_per_share(lp_token, block_identifier=samples.now)
    try:
        week_ago_price = price_per_share(lp_token, block_identifier=samples.week_ago)
    except:
        raise ApyError("crv", "insufficient data")

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)

    pool_apr = calculate_roi(now_point, week_ago_point)
    pool_apy = (((pool_apr / 365) + 1) ** 365) - 1

    # FIXME: crvANKR's pool apy going crazy
    if vault.vault.address == "0xE625F5923303f1CE7A43ACFEFd11fd12f30DbcA4":
        pool_apy = 0

    if type(vault) is VaultV2:
        contract = vault.vault
        keep_crv = sum([strategy.keepCRV() for strategy in vault.strategies if hasattr(strategy, "keepCRV")])
        performance = (contract.performanceFee() * 2) if hasattr(contract, "performanceFee") else 0
        management = contract.managementFee() if hasattr(contract, "managementFee") else 0
    else:
        strategy = vault.strategy
        strategist_performance = strategy.performanceFee() if hasattr(strategy, "performanceFee") else 0
        strategist_reward = strategy.strategistReward() if hasattr(strategy, "strategistReward") else 0
        treasury = strategy.treasuryFee() if hasattr(strategy, "treasuryFee") else 0
        keep_crv = strategy.keepCRV() if hasattr(strategy, "keepCRV") else 0

        performance = strategist_reward + strategist_performance + treasury
        management = 0

    keep_crv /= 1e4
    performance /= 1e4
    management /= 1e4

    lose_crv = 1 - keep_crv

    gross_farmed_apy = (
        (boosted_apr * keep_crv) + (((boosted_apr * lose_crv + reward_apr) / COMPOUNDING) + 1) ** COMPOUNDING
    ) - 1

    apy = (gross_farmed_apy + 1) * (pool_apy + 1) - 1

    net_curve_apr = (boosted_apr * lose_crv + reward_apr) * (1 - performance) - management

    net_farmed_apy = ((net_curve_apr / COMPOUNDING) + 1) ** COMPOUNDING - 1
    net_apy = (net_farmed_apy + 1) * (pool_apy + 1) - 1

    fees = ApyFees(performance=performance, management=management, keep_crv=keep_crv)
    composite = {
        "boost": boost,
        "pool_apy": pool_apy,
        "boosted_apr": boosted_apr,
        "base_apr": base_apr,
        "rewards_apr": reward_apr,
    }
    return Apy("crv", apy, net_apy, fees, composite=composite)
