import asyncio
import time

from y import ERC20, Contract
from y.prices import magic

from yearn.apy.common import SECONDS_PER_YEAR, ApySamples
from yearn.v1.vaults import VaultV1


async def get_staking_rewards_apr(vault, samples: ApySamples):
    now = int(time.time())
    if not vault or isinstance(vault, VaultV1):
        return 0

    staking_pools = await vault.registry.staking_pools
    vault_address = str(vault.vault)
    if vault_address not in staking_pools:
        return 0

    staking_pool = await Contract.coroutine(staking_pools[vault_address])
    if await staking_pool.periodFinish.coroutine() < now:
        return 0

    await vault.registry.load_vaults()
    rewards_vault = vault.registry._vaults[await staking_pool.rewardsToken.coroutine()]
    (
        reward_rate, 
        rewards_vault_scale, 
        total_supply_staked, 
        vault_scale, 
        vault_price, 
        rewards_asset_price
    ) = await asyncio.gather(
        staking_pool.rewardRate.coroutine(),
        ERC20(rewards_vault.vault, asynchronous=True).scale,
        staking_pool.totalSupply.coroutine(),
        ERC20(vault.vault, asynchronous=True).scale,
        magic.get_price(vault_address, sync=False),
        magic.get_price(rewards_vault.vault, sync=False),
    )
    if total_supply_staked == 0:
        return 0
    per_staking_token_rate = (reward_rate / rewards_vault_scale) / (total_supply_staked / vault_scale)
    rewards_vault_apy = (await rewards_vault.apy(samples)).net_apy
    emissions_apr = SECONDS_PER_YEAR * per_staking_token_rate * rewards_asset_price / vault_price
    return emissions_apr * (1 + rewards_vault_apy)
