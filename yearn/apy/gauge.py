import asyncio
import logging
from dataclasses import dataclass
from time import time

from brownie import ZERO_ADDRESS
from y import Contract
from y.time import get_block_timestamp

from yearn.apy.common import SECONDS_PER_YEAR, get_reward_token_price
from yearn.apy.curve.rewards import rewards
from yearn.typing import Address

logger = logging.getLogger(__name__)


@dataclass
class Gauge:
    lp_token: Address
    pool: Contract
    gauge: Contract
    gauge_weight: int
    gauge_inflation_rate: int
    gauge_working_supply: int

    def calculate_base_apr(self, max_boost, reward_price, pool_price_per_share, pool_token_price) -> float:
        return (
            self.gauge_inflation_rate
            * self.gauge_weight
            * (SECONDS_PER_YEAR / self.gauge_working_supply)
            * ((1.0 / max_boost) / pool_price_per_share)
            * reward_price
        ) / pool_token_price

    async def calculate_boost(self, max_boost, address, block=None) -> float:
        if address is None:
            balance, working_balance = 0, 0
        else:
            balance, working_balance = await asyncio.gather(
                self.gauge.balanceOf.coroutine(address, block_identifier=block),
                self.gauge.working_balances.coroutine(address, block_identifier=block),
            )
        if balance > 0:
            return  working_balance / ((1.0 / max_boost) * balance) or 1
        else:
            return max_boost

    def calculate_rewards_apr(self, pool_price_per_share, pool_token_price, kp3r=None, rkp3r=None, block=None) -> float:
        if hasattr(self.gauge, "reward_contract"):
            reward_address = self.gauge.reward_contract()
            if reward_address != ZERO_ADDRESS:
                return rewards(reward_address, pool_price_per_share, pool_token_price, block=block)

        elif hasattr(self.gauge, "reward_data"): # this is how new gauges, starting with MIM, show rewards
            # get our token
            # TODO: consider adding for loop with [gauge.reward_tokens(i) for i in range(gauge.reward_count())] for multiple rewards tokens
            gauge_reward_token = self.gauge.reward_tokens(0)
            if gauge_reward_token in [ZERO_ADDRESS]:
                logger.warn(f"no reward token for gauge {str(self.gauge)}")
            else:
                reward_data = self.gauge.reward_data(gauge_reward_token)
                rate = reward_data['rate']
                period_finish = reward_data['period_finish']
                total_supply = self.gauge.totalSupply()
                token_price = get_reward_token_price(gauge_reward_token, kp3r, rkp3r)
                current_time = time() if block is None else get_block_timestamp(block)
                if period_finish < current_time:
                    return 0
                else:
                    return (
                        (SECONDS_PER_YEAR * (rate / 1e18) * token_price) 
                        / ((pool_price_per_share / 1e18) * (total_supply / 1e18) * pool_token_price)
                    )

        return 0
