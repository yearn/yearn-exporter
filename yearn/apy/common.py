from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Optional

from brownie import web3

from yearn.utils import closest_block_after_timestamp
from semantic_version.base import Version


SECONDS_PER_YEAR = 31_556_952.0

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
    composite: Optional[Dict[str, float]] = None


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
    blocks_per_day = int((now - closest_block_after_timestamp((now_time - timedelta(days=7)).timestamp())) / 7)
    
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
        now = closest_block_after_timestamp(now_time.timestamp())
    week_ago = closest_block_after_timestamp((now_time - timedelta(days=7)).timestamp())
    month_ago = closest_block_after_timestamp((now_time - timedelta(days=31)).timestamp())
    return ApySamples(now, week_ago, month_ago)
