from time import time
from typing import Optional

from brownie import ZERO_ADDRESS
from y.prices import magic
from y.time import get_block_timestamp

from yearn.apy.common import SECONDS_PER_YEAR
from yearn.utils import contract


def rewards(address: str, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    staking_rewards = contract(address)
    if hasattr(staking_rewards, "periodFinish"):
        return staking(address, pool_price, base_asset_price, block=block)
    else:
        return multi(address, pool_price, base_asset_price, block=block)


def staking(address: str, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    staking_rewards = contract(address)
    end = staking_rewards.periodFinish(block_identifier=block)

    current_time = time() if block is None else get_block_timestamp(block)
    if end < current_time:
        return 0

    snx_address = staking_rewards.snx(block_identifier=block) if hasattr(staking_rewards, "snx") else None
    reward_token = staking_rewards.rewardToken(block_identifier=block) if hasattr(staking_rewards, "rewardToken") else None
    rewards_token = staking_rewards.rewardsToken(block_identifier=block) if hasattr(staking_rewards, "rewardsToken") else None

    token = reward_token or rewards_token or snx_address

    total_supply = staking_rewards.totalSupply(block_identifier=block) if hasattr(staking_rewards, "totalSupply") else 0
    rate = staking_rewards.rewardRate(block_identifier=block) if hasattr(staking_rewards, "rewardRate") else 0

    if token and rate:
        # Single reward token
        token_price = magic.get_price(token, block=block)
        return (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (
            (pool_price / 1e18) * (total_supply / 1e18) * base_asset_price
        )
    else:
        # Multiple reward tokens
        queue = 0
        apr = 0
        if not hasattr(staking_rewards, "rewardTokens"):
            print("no reward", staking_rewards.address)
            return apr
        try:
            token = staking_rewards.rewardTokens(queue, block_identifier=block)
        except ValueError:
            token = None
        while token and token != ZERO_ADDRESS:
            try:
                data = staking_rewards.rewardData(token, block_identifier=block)
            except ValueError:
                token = None
            rate = data.rewardRate / 1e18 if data else 0
            token_price = magic.get_price(token, block=block) or 0
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
            queue += 1
            try:
                token = staking_rewards.rewardTokens(queue, block_identifier=block)
            except ValueError:
                token = None
        return apr


def multi(address: str, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    multi_rewards = contract(address)

    total_supply = multi_rewards.totalSupply(block_identifier=block) if hasattr(multi_rewards, "totalSupply") else 0

    queue = 0
    apr = 0
    if hasattr(multi_rewards, "rewardsToken"):
        token = multi_rewards.rewardTokens(queue, block_identifier=block)
    else:
        token = None
    while token and token != ZERO_ADDRESS:
        try:
            data = multi_rewards.rewardData(token, block_identifier=block)
        except ValueError:
            token = None
        if data.periodFinish >= time():
            rate = data.rewardRate / 1e18 if data else 0
            token_price = magic.get_price(token, block=block) or 0
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
        queue += 1
        try:
            token = multi_rewards.rewardTokens(queue, block_identifier=block)
        except ValueError:
            token = None
    return apr
