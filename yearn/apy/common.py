from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from brownie import interface, web3
from y.time import closest_block_after_timestamp

SECONDS_PER_YEAR = 31_556_952.0
SECONDS_PER_WEEK = 7 * 24 * 3600
SECONDS_PER_MONTH = 30 * 24 * 3600

@dataclass
class SharePricePoint:
    block: int
    price: int


@dataclass
class ApyFees:
    performance: Optional[float] = None
    withdrawal: Optional[float] = None
    management: Optional[float] = None
    keep_crv: Optional[float] = None
    cvx_keep_crv: Optional[float] = None
    keep_velo: Optional[float] = None

@dataclass
class ApyBlocks:
    now: int
    week_ago: int
    month_ago: int
    inception: int

@dataclass
class ApyPoints:
    week_ago: float
    month_ago: float
    inception: float


@dataclass
class Apy:
    type: str
    gross_apr: float
    net_apy: float
    fees: ApyFees
    points: Optional[ApyPoints] = None
    blocks: Optional[ApyBlocks] = None
    composite: Optional[Dict[str, float]] = None
    error_reason: Optional[str] = None
    staking_rewards_apr: Optional[float] = 0


@dataclass
class ApySamples:
    now: int
    week_ago: int
    month_ago: int


class ApyError(ValueError):
    type: str
    message: str


def calculate_roi(after: SharePricePoint, before: SharePricePoint) -> float:
    # calculate our average blocks per day in the past week
    now = web3.eth.block_number
    now_time = datetime.today()
    blocks_per_day = int((now - closest_block_after_timestamp(int((now_time - timedelta(days=7)).timestamp()), True)) / 7)
    
    # calculate our annualized return for a vault
    pps_delta = (after.price - before.price) / (before.price or 1)
    block_delta = after.block - before.block
    days = block_delta / blocks_per_day
    annualized_roi = (1 + pps_delta) ** (365.2425 / days) - 1
    return annualized_roi


def get_samples(now_time: Optional[datetime] = None) -> ApySamples:
    if now_time is None:
        now_time = datetime.today()
        now = web3.eth.block_number
    else:
        now = closest_block_after_timestamp(int(now_time.timestamp()), True)
    week_ago = closest_block_after_timestamp(int((now_time - timedelta(days=7)).timestamp()), True)
    month_ago = closest_block_after_timestamp(int((now_time - timedelta(days=31)).timestamp()), True)
    return ApySamples(now, week_ago, month_ago)

def get_reward_token_price(reward_token, kp3r=None, rkp3r=None, block=None):
    from yearn.prices import magic

    # if the reward token is rKP3R we need to calculate it's price in 
    # terms of KP3R after the discount
    if str(reward_token) == rkp3r:
        rKP3R_contract = interface.rKP3R(reward_token)
        discount = rKP3R_contract.discount(block_identifier=block)
        return magic.get_price(kp3r, block=block) * (100 - discount) / 100
    else:
        return magic.get_price(reward_token, block=block)

def calculate_pool_apy(vault, price_per_share_function, samples) -> Tuple[float, float]:
    now_price = price_per_share_function(block_identifier=samples.now)
    try:
        week_ago_price = price_per_share_function(block_identifier=samples.week_ago)
    except ValueError:
        raise ApyError("common", "insufficient data")

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)

    # FIXME: crvANKR's pool apy going crazy
    if vault and vault.vault.address == "0xE625F5923303f1CE7A43ACFEFd11fd12f30DbcA4":
        return 0, 0

    # Curve USDT Pool yVault apr is way too high which fails the apy calculations with a OverflowError
    elif vault and vault.vault.address == "0x28a5b95C101df3Ded0C0d9074DB80C438774B6a9":
        return 0, 0

    else:
        pool_apr = calculate_roi(now_point, week_ago_point)
        return pool_apr, (((pool_apr / 365) + 1) ** 365) - 1
