from time import time
from itertools import count
from typing import Optional
from brownie import Contract

from yearn.apy.common import SECONDS_PER_YEAR
from yearn.utils import get_block_timestamp, contract

from yearn.prices.magic import get_price


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
    reward_token = _get_rewards_token(staking_rewards, block)

    token = reward_token or snx_address

    total_supply = staking_rewards.totalSupply(block_identifier=block) if hasattr(staking_rewards, "totalSupply") else 0
    rate = staking_rewards.rewardRate(block_identifier=block) if hasattr(staking_rewards, "rewardRate") else 0

    if token and rate:
        # Single reward token
        token_price = get_price(token, block=block)
        return (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (
            (pool_price / 1e18) * (total_supply / 1e18) * base_asset_price
        )
    else:
        # Multiple reward tokens or rate == 0
        apr = 0
        for queue in count():
            token = _get_rewards_token(staking_rewards, block, queue)
            if not token:
                break

            data = _get_rewards_data(token, block_identifier=block)

            rate = data.rewardRate / 1e18 if data else 0
            token_price = get_price(token, block=block) or 0
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
        return apr


def multi(address: str, pool_price: int, base_asset_price: int, block: Optional[int]=None) -> float:
    multi_rewards = contract(address)

    total_supply = multi_rewards.totalSupply(block_identifier=block) if hasattr(multi_rewards, "totalSupply") else 0

    apr = 0
    for queue in count():
        token = _get_rewards_token(multi_rewards, block, queue)
        if not token:
            break

        data = multi_rewards.rewardData(token, block_identifier=block)

        if data.periodFinish >= time():
            rate = data.rewardRate / 1e18 if data else 0
            token_price = get_price(token, block=block) or 0
            apr += SECONDS_PER_YEAR * rate * token_price / ((pool_price / 1e18) * (total_supply / 1e18) * token_price)
    return apr


def _get_rewards_data(base, token, block):
    if hasattr(base, "rewardData"):
        return base.rewardData(token, block_identifier=block)
    else:
        return None


def _get_rewards_token(base, block, queue=None, has_params=True):
    try:
        if hasattr(base, "rewardToken"):
            if not has_params:
                # some tokens don't support params
                return base.rewardToken()

            if queue is None:
                return base.rewardToken(block_identifier=block)
            else:
                return base.rewardToken(queue, block_identifier=block)
        elif hasattr(base, "rewardsToken"):
            if not has_params:
                # some tokens don't support params
                return base.rewardsToken()

            if queue is None:
                return base.rewardsToken(block_identifier=block)
            else:
                return base.rewardsToken(queue, block_identifier=block)
        else:
            return None
    except TypeError as e:
        if has_params:
            # do one recursive call if the first call failed due to the method not supporting params
            return _get_rewards_token(base, None, queue=None, has_params=False)
        else:
            logger.error(e)
            return None
