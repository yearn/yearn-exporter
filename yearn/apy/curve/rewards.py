from time import time

from brownie import Contract, ZERO_ADDRESS

from yearn.apy.common import SECONDS_PER_YEAR

from yearn.prices.magic import get_price


def rewards(address: str, pool_price: int, base_asset_price: int) -> float:
    staking_rewards = Contract(address)
    if hasattr(staking_rewards, "periodFinish"):
        return staking(address, pool_price, base_asset_price)
    else:
        return multi(address, pool_price, base_asset_price)


def staking(address: str, pool_price: int, base_asset_price: int) -> float:
    staking_rewards = Contract(address)
    end = staking_rewards.periodFinish()
    if end < time():
        return 0

    snx_address = staking_rewards.snx() if hasattr(staking_rewards, "snx") else None
    reward_token = staking_rewards.rewardToken() if hasattr(staking_rewards, "rewardToken") else None
    rewards_token = staking_rewards.rewardsToken() if hasattr(staking_rewards, "rewardsToken") else None

    token = reward_token or rewards_token or snx_address

    total_supply = staking_rewards.totalSupply() if hasattr(staking_rewards, "totalSupply") else 0
    rate = staking_rewards.rewardRate() if hasattr(staking_rewards, "rewardRate") else 0

    if token and rate:
        # Single reward token
        token_price = get_price(token)
        return (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (
            (pool_price / 1e18) * (total_supply / 1e18) * base_asset_price
        )
    else:
        # Multiple reward tokens
        queue = 0
        apr = 0
        try:
            token = staking_rewards.rewardTokens(queue)
        except ValueError:
            token = None
        while token and token != ZERO_ADDRESS:
            try:
                data = staking_rewards.rewardData(token)
            except ValueError:
                token = None
            rate = data.rewardRate / 1e18 if data else 0
            token_price = get_price(token) or 0
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
            queue += 1
            try:
                token = staking_rewards.rewardTokens(queue)
            except ValueError:
                token = None
        return apr


def multi(address: str, pool_price: int, base_asset_price: int) -> float:
    multi_rewards = Contract(address)

    total_supply = multi_rewards.totalSupply() if hasattr(multi_rewards, "totalSupply") else 0

    queue = 0
    apr = 0
    try:
        token = multi_rewards.rewardTokens(queue)
    except ValueError:
        token = None
    while token and token != ZERO_ADDRESS:
        try:
            data = multi_rewards.rewardData(token)
        except ValueError:
            token = None
        if data.periodFinish >= time():
            rate = data.rewardRate / 1e18 if data else 0
            token_price = get_price(token) or 0
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
        queue += 1
        try:
            token = multi_rewards.rewardTokens(queue)
        except ValueError:
            token = None
    return apr
