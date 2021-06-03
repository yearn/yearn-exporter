from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Optional

from brownie import web3

from yearn.utils import closest_block_after_timestamp

SECONDS_PER_BLOCK = 13.25
SECONDS_PER_YEAR = 31_536_000.0
BLOCK_PER_DAY = (60 * 60 * 24) / SECONDS_PER_BLOCK


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
    apy: float
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
    delta = (after.price - before.price) / (before.price or 1)
    block_delta = after.block - before.block
    derivative = delta / block_delta
    annualized = derivative * BLOCK_PER_DAY * 365
    return annualized


def get_samples() -> ApySamples:
    today = datetime.today()
    now = web3.eth.block_number
    week_ago = closest_block_after_timestamp((today - timedelta(days=7)).timestamp())
    month_ago = closest_block_after_timestamp((today - timedelta(days=31)).timestamp())
    return ApySamples(now, week_ago, month_ago)
