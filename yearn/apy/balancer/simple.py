import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pprint import pformat
from typing import TYPE_CHECKING, Dict

from async_lru import alru_cache
from brownie import chain
from y import ERC20, Contract, Network, magic
from y.datatypes import Address
from y.prices.dex.balancer.v2 import BalancerV2Pool, balancer
from y.time import closest_block_after_timestamp_async
from y.utils.dank_mids import dank_w3

from yearn.apy.booster import get_booster_fee
from yearn.apy.common import (SECONDS_PER_YEAR, Apy, ApyBlocks, ApyError,
                              ApyFees, ApySamples)
from yearn.apy.gauge import Gauge
from yearn.debug import Debug

if TYPE_CHECKING:
    from yearn.v2.vaults import Vault

logger = logging.getLogger(__name__)

@dataclass
class AuraAprData:
    boost: float = 0
    bal_apr: float = 0
    aura_apr: float = 0
    swap_fees_apr: float = 0
    bonus_rewards_apr: float = 0
    gross_apr: float = 0
    net_apr: float = 0
    debt_ratio: float = 0

addresses = {
    Network.Mainnet: {
        'gauge_factory': '0x4E7bBd911cf1EFa442BC1b2e9Ea01ffE785412EC',
        'gauge_controller': '0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD',
        'voter': '0xc999dE72BFAFB936Cb399B94A8048D24a27eD1Ff',
        'bal': '0xba100000625a3754423978a60c9317c58a424e3D',
        'aura': '0xC0c293ce456fF0ED870ADd98a0828Dd4d2903DBF',
        'booster': '0xA57b8d98dAE62B26Ec3bcC4a365338157060B234',
        'booster_voter': '0xaF52695E1bB01A16D33D7194C28C42b10e0Dbec2',
    }
}

MAX_BOOST = 2.5
COMPOUNDING = 52

@alru_cache
async def get_pool(poolId: bytes) -> BalancerV2Pool:
    return BalancerV2Pool((await balancer.vaults[0].contract.getPool.coroutine(poolId.hex()))[0])

def is_aura_vault(vault: "Vault") -> bool:
    return len(vault.strategies) == 1 and 'aura' in vault.strategies[0].name.lower()
    
async def get_gauge(token) -> Contract:
    gauges = await get_all_gauges()
    return gauges[token]

_ignore_gauges = ["SingleRecipientGauge", "ArbitrumRootGauge", "GnosisRootGauge", "OptimismRootGauge", "PolygonRootGauge", "PolygonZkEVMRootGauge"]

@alru_cache
async def get_all_gauges() -> Dict[Address, Contract]:
    gauge_controller = await Contract.coroutine(addresses[chain.id]['gauge_controller'])
    num_gauges = await gauge_controller.n_gauges.coroutine()
    gauges = await asyncio.gather(*[gauge_controller.gauges.coroutine(i) for i in range(num_gauges)])
    gauges = await asyncio.gather(*[Contract.coroutine(gauge) for gauge in gauges])
    gauges = [gauge for gauge in gauges if gauge._name not in _ignore_gauges]
    for gauge in gauges:
        if not hasattr(gauge, 'lp_token'):
            logger.warning(f'gauge {gauge} has no `lp_token` method')
            gauges.remove(gauge)
    return {gauge.lp_token(): gauge for gauge in gauges}

async def simple(vault, samples: ApySamples) -> Apy:
    if chain.id != Network.Mainnet: 
        raise ApyError('bal', 'chain not supported')
    if not is_aura_vault(vault): 
        raise ApyError('bal', 'vault not supported')

    now = samples.now
    pool = await Contract.coroutine(vault.token.address)
    
    try:
        gauge = await get_gauge(vault.token.address)
    except KeyError as e:
        raise ApyError('bal', 'gauge factory indicates no gauge exists') from e
    
    try:
        gauge_inflation_rate = await gauge.inflation_rate.coroutine(block_identifier=now)
    except AttributeError as e:
        raise ApyError('bal', f'gauge {gauge} {str(e)[str(e).find("object"):]}') from e

    gauge_working_supply = await gauge.working_supply.coroutine(block_identifier=now)
    if gauge_working_supply == 0:
        raise ApyError('bal', 'gauge working supply is zero')
    
    gauge_controller = await Contract.coroutine(addresses[chain.id]['gauge_controller'])
    gauge_weight = gauge_controller.gauge_relative_weight.call(gauge.address, block_identifier=now)

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    return await calculate_simple(
        vault,
        Gauge(pool.address, pool, gauge, gauge_weight, gauge_inflation_rate, gauge_working_supply),
        samples
    )

async def calculate_simple(vault, gauge: Gauge, samples: ApySamples) -> Apy:
    if not vault: raise ApyError('bal', 'apy preview not supported')

    now = samples.now
    pool_token_price, (performance_fee, management_fee, keep_bal) = await asyncio.gather(
        magic.get_price(gauge.lp_token, block=now, sync=False),
        get_vault_fees(vault, block=now),
    )

    apr_data = await get_current_aura_apr(
        vault, gauge,
        pool_token_price,
        block=now
    )
    if apr_data.bal_apr > 1000 or apr_data.aura_apr > 1000:
        raise ApyError('aura', f'apr data too big {apr_data}')

    gross_apr = apr_data.gross_apr * apr_data.debt_ratio

    net_booster_apr = apr_data.net_apr * (1 - performance_fee) - management_fee
    net_booster_apy = float(Decimal(1 + (net_booster_apr / COMPOUNDING)) ** COMPOUNDING - 1)
    net_apy = net_booster_apy

    fees = ApyFees(
        performance=performance_fee, 
        management=management_fee, 
        keep_crv=keep_bal, 
        cvx_keep_crv=keep_bal
    )

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    composite = {
        "boost": apr_data.boost,
        "bal_rewards_apr": apr_data.bal_apr,
        "aura_rewards_apr": apr_data.aura_apr,
        "swap_fees_apr": apr_data.swap_fees_apr,
        "bonus_rewards_apr": apr_data.bonus_rewards_apr,
        "aura_gross_apr": apr_data.gross_apr,
        "aura_net_apr": apr_data.net_apr,
        "booster_net_apr": net_booster_apr,
    }

    try:  # maybe this last arg should just be optional?
        blocks = ApyBlocks(
            samples.now, 
            samples.week_ago, 
            samples.month_ago, 
            vault.reports[0].block_number
        )
    except IndexError:
        blocks = None

    return Apy('aura', gross_apr, net_apy, fees, composite=composite, blocks=blocks)

async def get_current_aura_apr(
        vault,
        gauge,
        pool_token_price,
        block=None
) -> AuraAprData:
    """Calculate the current APR as opposed to projected APR like we do with CRV-CVX"""
    strategy = vault.strategies[0].strategy
    debt_ratio, booster, booster_boost = await asyncio.gather(
        get_debt_ratio(vault, strategy),
        Contract.coroutine(addresses[chain.id]['booster']),
        gauge.calculate_boost(MAX_BOOST, addresses[chain.id]['booster_voter'], block),
    )
    booster_fee = get_booster_fee(booster, block)

    bal_price, aura_price, rewards = await asyncio.gather(
        magic.get_price(addresses[chain.id]['bal'], block=block, sync=False),
        magic.get_price(addresses[chain.id]['aura'], block=block, sync=False),
        strategy.rewardsContract.coroutine(),
    )

    rewards, bal_rewards_total_supply, aura_rewards_total_supply = await asyncio.gather(
        Contract.coroutine(rewards),
        ERC20(gauge.gauge, asynchronous=True).total_supply_readable(),
        ERC20(rewards, asynchronous=True).total_supply_readable(),
    )
    
    # find bal rewards tvl
    bal_rewards_tvl = pool_token_price * bal_rewards_total_supply
    aura_rewards_tvl = pool_token_price * aura_rewards_total_supply
    if not aura_rewards_tvl:
        raise ApyError('bal', 'rewards tvl is 0')

    reward_rate, scale = await asyncio.gather(rewards.rewardRate.coroutine(), ERC20(rewards, asynchronous=True).scale)
    logger.info(f'strategy: {strategy}  rewards: {rewards}  reward rate: {reward_rate}  scale: {scale}')
    bal_rewards_per_year = (reward_rate / scale) * SECONDS_PER_YEAR
    bal_rewards_per_year_usd =  bal_rewards_per_year * bal_price
    bal_rewards_apr = bal_rewards_per_year_usd / bal_rewards_tvl

    aura_emission_rate, swap_fees_apr, bonus_rewards_apr = await asyncio.gather(
        get_aura_emission_rate(block),
        calculate_24hr_swap_fees_apr(gauge.pool, block),
        get_bonus_rewards_apr(rewards, aura_rewards_tvl),
    )
    aura_rewards_per_year = bal_rewards_per_year * aura_emission_rate
    aura_rewards_per_year_usd = aura_rewards_per_year * aura_price
    aura_rewards_apr = aura_rewards_per_year_usd / aura_rewards_tvl

    net_apr = (
        bal_rewards_apr 
        + aura_rewards_apr 
        + swap_fees_apr 
        + bonus_rewards_apr
    )

    gross_apr = (
        (bal_rewards_apr / (1 - booster_fee)) 
        + aura_rewards_apr 
        + swap_fees_apr 
        + bonus_rewards_apr
    )

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    return AuraAprData(
        booster_boost,
        bal_rewards_apr,
        aura_rewards_apr,
        swap_fees_apr,
        bonus_rewards_apr,
        gross_apr,
        net_apr,
        debt_ratio
    )

async def get_bonus_rewards_apr(rewards, rewards_tvl, block=None):
    result = 0
    for index in range(rewards.extraRewardsLength(block_identifier=block)):
        extra_rewards = await Contract.coroutine(await rewards.extraRewards.coroutine(index))
        reward_token = extra_rewards
        if hasattr(extra_rewards, 'rewardToken'):
            reward_token = await Contract.coroutine(await extra_rewards.rewardToken.coroutine())

        extra_reward_rate, reward_token_scale, reward_token_price = await asyncio.gather(
            extra_rewards.rewardRate.coroutine(block_identifier=block),
            ERC20(reward_token, asynchronous=True).scale,
            magic.get_price(reward_token, block=block, sync=False),
        )
        extra_rewards_per_year = (extra_reward_rate / reward_token_scale) * SECONDS_PER_YEAR
        extra_rewards_per_year_usd = extra_rewards_per_year * reward_token_price
        result += extra_rewards_per_year_usd / rewards_tvl
    return result

async def get_vault_fees(vault, block=None):
    if vault:
        vault_contract = vault.vault
        if len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, 'keepBAL'):
            keep_bal = await vault.strategies[0].strategy.keepBAL.coroutine(block_identifier=block) / 1e4
        else:
            keep_bal = 0
        performance = await vault_contract.performanceFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault_contract, "performanceFee") else 0
        management = await vault_contract.managementFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault_contract, "managementFee") else 0

    else:
        # used for APY calculation previews
        performance = 0.1
        management = 0
        keep_bal = 0
    
    return performance, management, keep_bal

async def get_aura_emission_rate(block=None) -> float:
    aura = await Contract.coroutine(addresses[chain.id]['aura'])
    initial_mint, supply, max_supply = await asyncio.gather(
        aura.INIT_MINT_AMOUNT.coroutine(),
        aura.totalSupply.coroutine(block_identifier=block),
        aura.EMISSIONS_MAX_SUPPLY.coroutine(),
    )
    max_supply += initial_mint

    if supply <= max_supply:
        total_cliffs, reduction_per_cliff, minter_minted = await asyncio.gather(
            aura.totalCliffs.coroutine(block_identifier=block),
            aura.reductionPerCliff.coroutine(block_identifier=block),
            get_aura_minter_minted(block),
        )
        current_cliff = (supply - initial_mint - minter_minted) / reduction_per_cliff
        reduction =  2.5 * (total_cliffs - current_cliff) + 700

        if os.getenv('DEBUG', None):
            logger.info(pformat(Debug().collect_variables(locals())))

        return reduction / total_cliffs
    else:
        if os.getenv('DEBUG', None):
            logger.info(pformat(Debug().collect_variables(locals())))

        return 0

async def get_aura_minter_minted(block=None) -> float:
    """According to Aura's docs you should use the minterMinted field when calculating the
    current aura emission rate. The minterMinted field is private in the contract though!?
    So get it by storage slot"""

    # convert HexBytes to int
    hb = await dank_w3.eth.get_storage_at(addresses[chain.id]['aura'], 7, block_identifier=block)
    return int(hb.hex(), 16)

async def get_debt_ratio(vault, strategy) -> float:
    info = await vault.vault.strategies.coroutine(strategy)
    return info[2] / 1e4

async def calculate_24hr_swap_fees_apr(pool: Contract, block=None):
    if not block: block = await closest_block_after_timestamp_async(datetime.today(), True)
    yesterday = await closest_block_after_timestamp_async((datetime.today() - timedelta(days=1)), True)
    pool = BalancerV2Pool(pool, asynchronous=True)
    swap_fees_now, swap_fees_yesterday, pool_tvl = await asyncio.gather(
        get_total_swap_fees(await pool.id, block),
        get_total_swap_fees(await pool.id, yesterday),
        pool.get_tvl(block=block),
    )
    swap_fees_delta = float(swap_fees_now) - float(swap_fees_yesterday)
    return swap_fees_delta * 365 / float(pool_tvl)

async def get_total_swap_fees(pool_id: bytes, block: int) -> int:
    pool = await get_pool(pool_id)
    return await pool.contract.getRate.coroutine(block_identifier=block) / 10 ** 18
    