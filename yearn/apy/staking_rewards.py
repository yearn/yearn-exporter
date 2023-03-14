import time
from yearn.prices import magic
from yearn.apy.common import ApySamples, SECONDS_PER_YEAR
from yearn.utils import contract

def get_staking_rewards_apy(vault, samples: ApySamples):
    vault_address = str(vault.vault)
    if vault_address not in vault.registry.staking_pools:
        return 0

    staking_pool = contract(vault.registry.staking_pools[vault_address])
    if staking_pool.periodFinish() < time.time():
        return 0

    rewards_vault = vault.registry._vaults[staking_pool.rewardsToken()]
    per_staking_token_rate = (staking_pool.rewardRate() / 10**rewards_vault.vault.decimals()) / (staking_pool.totalSupply() / 10**vault.vault.decimals())

    vault_price = magic.get_price(vault_address)
    rewards_asset_price = magic.get_price(rewards_vault.vault)

    emissions_apr = SECONDS_PER_YEAR * per_staking_token_rate * rewards_asset_price / vault_price
    rewards_vault_apy = rewards_vault.apy(samples).net_apy

    return emissions_apr * (1 + rewards_vault_apy)
