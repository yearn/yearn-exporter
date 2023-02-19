from dataclasses import dataclass
from brownie import Contract
from yearn.typing import Address
from yearn.apy.common import SECONDS_PER_YEAR


@dataclass
class Gauge:
    lp_token: Address
    pool: Contract
    gauge: Contract
    gauge_weight: int
    gauge_inflation_rate: int
    gauge_working_supply: int

    def calculate_base_apr(self, per_max_boost, reward_price, pool_price_per_share, pool_token_price) -> float:
        return (
            self.gauge_inflation_rate
            * self.gauge_weight
            * (SECONDS_PER_YEAR / self.gauge_working_supply)
            * (per_max_boost / pool_price_per_share)
            * reward_price
        ) / pool_token_price
