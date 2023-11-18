import asyncio
from time import time
from typing import Optional

from brownie import ZERO_ADDRESS
from y import Contract
from y.prices import magic
from y.time import get_block_timestamp_async

from yearn.apy.common import SECONDS_PER_YEAR


async def rewards(address: str, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    staking_rewards = await Contract.coroutine(address)
    if hasattr(staking_rewards, "periodFinish"):
        return await staking(staking_rewards, pool_price, base_asset_price, block=block)
    else:
        return await multi(address, pool_price, base_asset_price, block=block)


async def staking(staking_rewards: Contract, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    end = await staking_rewards.periodFinish.coroutine(block_identifier=block)

    current_time = time() if block is None else await get_block_timestamp_async(block)
    if end < current_time:
        return 0

    snx_address = await staking_rewards.snx.coroutine(block_identifier=block) if hasattr(staking_rewards, "snx") else None
    reward_token = None
    if hasattr(staking_rewards, "rewardToken"):
        reward_token = await staking_rewards.rewardToken.coroutine(block_identifier=block)
    elif hasattr(staking_rewards, "rewardsToken"):
        reward_token = await staking_rewards.rewardsToken.coroutine(block_identifier=block)

    token = reward_token or snx_address

    total_supply = await staking_rewards.totalSupply.coroutine(block_identifier=block) if hasattr(staking_rewards, "totalSupply") else 0
    rate = await staking_rewards.rewardRate.coroutine(block_identifier=block) if hasattr(staking_rewards, "rewardRate") else 0

    if token and rate:
        # Single reward token
        token_price = float(await magic.get_price(token, block=block, sync=False))
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
            token = await staking_rewards.rewardTokens.coroutine(queue, block_identifier=block)
        except ValueError:
            token = None
        while token and token != ZERO_ADDRESS:
            try:
                data = await staking_rewards.rewardData.coroutine(token, block_identifier=block)
            except ValueError:
                token = None
            rate = data.rewardRate / 1e18 if data else 0
            token_price = float(await magic.get_price(token, block=block, sync=False) or 0)
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
            queue += 1
            try:
                token = await staking_rewards.rewardTokens.coroutine(queue, block_identifier=block)
            except ValueError:
                token = None
        return apr


async def multi(address: str, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    multi_rewards = await Contract.coroutine(address)

    total_supply = await multi_rewards.totalSupply.coroutine(block_identifier=block) if hasattr(multi_rewards, "totalSupply") else 0

    queue = 0
    apr = 0
    if hasattr(multi_rewards, "rewardsToken"):
        token = await multi_rewards.rewardTokens.coroutine(queue, block_identifier=block)
    else:
        token = None
    while token and token != ZERO_ADDRESS:
        try:
            data = await multi_rewards.rewardData.coroutine(token, block_identifier=block)
        except ValueError:
            token = None
        if data.periodFinish >= time():
            rate = data.rewardRate / 1e18 if data else 0
            token_price = float(await magic.get_price(token, block=block, sync=False) or 0)
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
        queue += 1
        try:
            token = await multi_rewards.rewardTokens.coroutine(queue, block_identifier=block)
        except ValueError:
            token = None
    return apr
