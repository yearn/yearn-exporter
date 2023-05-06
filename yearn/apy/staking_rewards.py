import time

from y.prices import magic

from yearn.apy.common import SECONDS_PER_YEAR, ApySamples
from yearn.utils import contract
from yearn.v1.vaults import VaultV1


def get_staking_rewards_apr(vault, samples: ApySamples):
    now = int(time.time())
    if not vault or isinstance(vault, VaultV1):
        return 0

    vault_address = str(vault.vault)
    if vault_address not in vault.registry.staking_pools:
        return 0

    staking_pool = contract(vault.registry.staking_pools[vault_address])
    if staking_pool.periodFinish() < now:
        return 0

    rewards_vault = vault.registry._vaults[staking_pool.rewardsToken()]
    per_staking_token_rate = (staking_pool.rewardRate() / 10**rewards_vault.vault.decimals()) / (staking_pool.totalSupply() / 10**vault.vault.decimals())

    vault_price = magic.get_price(vault_address)
    rewards_asset_price = magic.get_price(rewards_vault.vault)
    rewards_vault_apy = rewards_vault.apy(samples).net_apy

    emissions_apr = SECONDS_PER_YEAR * per_staking_token_rate * rewards_asset_price / vault_price
    return emissions_apr * (1 + rewards_vault_apy)
