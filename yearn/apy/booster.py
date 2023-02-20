from time import time

from yearn.apy.common import get_reward_token_price, SECONDS_PER_YEAR
from yearn.utils import contract, get_block_timestamp

def get_booster_fee(booster, block=None) -> float:
    """The fee % that the booster charges on yield."""
    lock_incentive = booster.lockIncentive(block_identifier=block)
    staker_incentive = booster.stakerIncentive(block_identifier=block)
    earmark_incentive = booster.earmarkIncentive(block_identifier=block)
    platform_fee = booster.platformFee(block_identifier=block)
    return (lock_incentive + staker_incentive + earmark_incentive + platform_fee) / 1e4

def get_booster_reward_apr(
        strategy, 
        booster, 
        pool_price_per_share, 
        pool_token_price,
        kp3r=None, rkp3r=None,
        block=None
) -> float:
    """The cumulative apr of all extra tokens that are emitted by depositing 
    to the booster, assuming they will be sold for profit.
    """
    if hasattr(strategy, "id"):
        # Convex hBTC strategy uses id rather than pid - 0x7Ed0d52C5944C7BF92feDC87FEC49D474ee133ce
        pid = strategy.id()
    else:
        pid = strategy.pid()

    # get bonus rewards from rewards contract
    # even though rewards are in different tokens,
    # the pool info field is "crvRewards" for both convex and aura
    rewards_contract = contract(booster.poolInfo(pid)['crvRewards'])
    rewards_length = rewards_contract.extraRewardsLength()
    current_time = time() if block is None else get_block_timestamp(block)
    if rewards_length == 0:
        return 0

    total_apr = 0
    for x in range(rewards_length):
        virtual_rewards_pool = contract(rewards_contract.extraRewards(x))
        if virtual_rewards_pool.periodFinish() > current_time:
            reward_token = virtual_rewards_pool.rewardToken()
            reward_token_price = get_reward_token_price(reward_token, kp3r, rkp3r, block)
            reward_apr = (
                (virtual_rewards_pool.rewardRate() * SECONDS_PER_YEAR * reward_token_price) 
                / (pool_token_price * (pool_price_per_share / 1e18) * virtual_rewards_pool.totalSupply())
            )
            total_apr += reward_apr

    return total_apr
