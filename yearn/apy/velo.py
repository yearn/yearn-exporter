import logging
import os
from functools import lru_cache
from pprint import pformat
from time import time
from typing import TYPE_CHECKING, Optional

from brownie import ZERO_ADDRESS, chain
from y import Contract, Network

from yearn.apy.common import SECONDS_PER_YEAR, Apy, ApyFees
from yearn.debug import Debug
from yearn.prices import magic
from yearn.utils import get_block_timestamp

if TYPE_CHECKING:
    from yearn.v2.vaults import Vault

logger = logging.getLogger(__name__)

COMPOUNDING = 365

registry = Contract("0x41c914ee0c7e1a5edcd0295623e6dc557b5abf3c") if Network(chain.id) == Network.Optimism else None

@lru_cache
def get_staking_pool(underlying: str) -> Optional[Contract]:
    if Network(chain.id) == Network.Optimism:
        staking_pool = registry.gauges(underlying)
        return None if staking_pool == ZERO_ADDRESS else Contract(staking_pool)
        
def staking(vault: "Vault", staking_rewards: Contract, block: Optional[int]=None) -> float:
    end = staking_rewards.periodFinish(block_identifier=block)
    current_time = time() if block is None else get_block_timestamp(block)
    total_supply = staking_rewards.totalSupply(block_identifier=block) if hasattr(staking_rewards, "totalSupply") else 0
    rate = staking_rewards.rewardRate(block_identifier=block) if hasattr(staking_rewards, "rewardRate") else 0
    performance = vault.vault.performanceFee(block_identifier=block) / 1e4 if hasattr(vault.vault, "performanceFee") else 0
    management = vault.vault.managementFee(block_identifier=block) / 1e4 if hasattr(vault.vault, "managementFee") else 0
    fees = ApyFees(performance=performance, management=management)
    
    if end < current_time or total_supply == 0 or rate == 0:
        return Apy("v2:velo_unpopular", gross_apr=0, net_apy=0, fees=fees)
    
    pool_price = magic.get_price(vault.token.address, block=block)
    reward_token = staking_rewards.rewardToken(block_identifier=block) if hasattr(staking_rewards, "rewardToken") else None
    token = reward_token
    token_price = magic.get_price(token, block=block)
    
    gross_apr = (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (pool_price * (total_supply / 1e18))
    
    net_apr = gross_apr * (1 - performance) - management 
    net_apy = (1 + (net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    if os.getenv("DEBUG", None):
        logger.info(pformat(Debug().collect_variables(locals())))
    return Apy("v2:velo", gross_apr=gross_apr, net_apy=net_apy, fees=fees)
