import time
from dataclasses import dataclass
from yearn.prices import magic
from yearn.apy.common import SECONDS_PER_YEAR, SECONDS_PER_MONTH, SECONDS_PER_WEEK, ApySamples
from yearn.utils import contract, get_block_timestamp
from yearn.v1.vaults import VaultV1

@dataclass
class StakingRewards:
    inception_apy: float
    monthly_apy: float
    weekly_apy: float

def get_staking_rewards(vault, samples: ApySamples, inception_block):
    staking_rewards = StakingRewards(0, 0, 0)
    now = int(time.time())
    if isinstance(vault, VaultV1):
        return staking_rewards

    vault_address = str(vault.vault)
    if vault_address not in vault.registry.staking_pools:
        return staking_rewards

    staking_pool = contract(vault.registry.staking_pools[vault_address])
    if staking_pool.periodFinish() < now:
        return staking_rewards

    rewards_vault = vault.registry._vaults[staking_pool.rewardsToken()]
    per_staking_token_rate = (staking_pool.rewardRate() / 10**rewards_vault.vault.decimals()) / (staking_pool.totalSupply() / 10**vault.vault.decimals())

    vault_price = magic.get_price(vault_address)
    rewards_asset_price = magic.get_price(rewards_vault.vault)
    rewards_vault_apy = rewards_vault.apy(samples).net_apy

    base_apr = (1 + rewards_vault_apy) * per_staking_token_rate * rewards_asset_price / vault_price

    seconds_since_inception = now - int(get_block_timestamp(inception_block))
    inception_apy = seconds_since_inception * base_apr
    monthly_apy = SECONDS_PER_MONTH * base_apr
    weekly_apy = SECONDS_PER_WEEK * base_apr

    return StakingRewards(inception_apy, monthly_apy, weekly_apy)
