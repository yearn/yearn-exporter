import logging
import os
from pprint import pformat
from time import time
from typing import TYPE_CHECKING, Optional

from async_lru import alru_cache
from brownie import ZERO_ADDRESS, chain
from y import Contract, Network, magic
from y.time import get_block_timestamp_async

from yearn.apy.common import SECONDS_PER_YEAR, Apy, ApyFees, ApyPoints, ApySamples
from yearn.debug import Debug

if TYPE_CHECKING:
    from yearn.v2.vaults import Vault

logger = logging.getLogger(__name__)

COMPOUNDING = 365

voter = Contract("0x41c914ee0c7e1a5edcd0295623e6dc557b5abf3c") if Network(chain.id) == Network.Base else None

@alru_cache
async def get_staking_pool(underlying: str) -> Optional[Contract]:
    if Network(chain.id) == Network.Base:
        staking_pool = await voter.gauges.coroutine(underlying)
        return None if staking_pool == ZERO_ADDRESS else await Contract.coroutine(staking_pool)
        
async def staking(vault: "Vault", staking_rewards: Contract, samples: ApySamples, block: Optional[int]=None) -> float:
    if len(vault.strategies) == 0:
        return Apy("v2:aero_no_strats", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))

    end = await staking_rewards.periodFinish.coroutine(block_identifier=block)
    current_time = time() if block is None else await get_block_timestamp_async(block)
    total_supply = await staking_rewards.totalSupply.coroutine(block_identifier=block) if hasattr(staking_rewards, "totalSupply") else 0
    rate = await staking_rewards.rewardRate.coroutine(block_identifier=block) if hasattr(staking_rewards, "rewardRate") else 0
    performance = await vault.vault.performanceFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault.vault, "performanceFee") else 0
    management = await vault.vault.managementFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault.vault, "managementFee") else 0
    # since its a fork we still call it keepVELO
    keep = await vault.strategies[0].strategy.localKeepVELO.coroutine(block_identifier=block) / 1e4 if hasattr(vault.strategies[0].strategy, "localKeepVELO") else 0
    rate = rate * (1 - keep)
    fees = ApyFees(performance=performance, management=management, keep_velo=keep)

    if end < current_time or total_supply == 0 or rate == 0:
        return Apy("v2:aero_unpopular", gross_apr=0, net_apy=0, fees=fees)
    pool_price = await magic.get_price(vault.token.address, block=block, sync=False)
    reward_token = await staking_rewards.rewardToken.coroutine(block_identifier=block) if hasattr(staking_rewards, "rewardToken") else None
    token = reward_token
    token_price = await magic.get_price(token, block=block, sync=False)
    
    gross_apr = (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (pool_price * (total_supply / 1e18))
    
    net_apr = gross_apr * (1 - performance) - management 
    net_apy = (1 + (net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    from yearn.apy.staking_rewards import get_staking_rewards_apr
    staking_rewards_apr = await get_staking_rewards_apr(vault, samples)
    if os.getenv("DEBUG", None):
        logger.info(pformat(Debug().collect_variables(locals())))
    return Apy("v2:aero", gross_apr=gross_apr, net_apy=net_apy, fees=fees, staking_rewards_apr=staking_rewards_apr)
