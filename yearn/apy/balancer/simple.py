import logging
import os
from pprint import pformat

from brownie import chain, web3
from dataclasses import dataclass
from semantic_version import Version

from yearn.apy.common import Apy, ApyBlocks, ApyError, ApyFees, ApySamples, calculate_pool_apy, SECONDS_PER_YEAR
from yearn.apy.booster import get_booster_fee, get_booster_reward_apr
from yearn.apy.gauge import Gauge
from yearn.debug import Debug
from yearn.networks import Network
from yearn.prices import magic
from yearn.utils import contract


logger = logging.getLogger(__name__)

@dataclass
class AuraAprData:
    boost: float = 0
    bal_apr: float = 0
    aura_apr: float = 0
    extra_rewards_apr: float = 0
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
        'booster_voter': '0xaF52695E1bB01A16D33D7194C28C42b10e0Dbec2'
    }
}

MAX_BOOST = 2.5
COMPOUNDING = 52

def is_aura_vault(vault):
    return len(vault.strategies) == 1 and 'aura' in vault.strategies[0].name.lower()

def simple(vault, samples: ApySamples) -> Apy:
    if chain.id != Network.Mainnet: raise ApyError('bal', 'chain not supported')
    if not is_aura_vault(vault): raise ApyError('bal', 'vault not supported')

    now = samples.now
    pool = contract(vault.token.address)
    gauge_factory = contract(addresses[chain.id]['gauge_factory'])
    gauge = contract(gauge_factory.getPoolGauge(pool.address))
    gauge_inflation_rate = gauge.inflation_rate(block_identifier=now)

    gauge_working_supply = gauge.working_supply(block_identifier=now)
    if gauge_working_supply == 0:
        raise ApyError('bal', 'gauge working supply is zero')

    gauge_controller = contract(addresses[chain.id]['gauge_controller'])
    gauge_weight = gauge_controller.gauge_relative_weight.call(gauge.address, block_identifier=now)

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    return calculate_simple(
        vault,
        Gauge(pool.address, pool, gauge, gauge_weight, gauge_inflation_rate, gauge_working_supply),
        samples
    )

def calculate_simple(vault, gauge: Gauge, samples: ApySamples) -> Apy:
    if not vault: raise ApyError('bal', 'apy preview not supported')

    now = samples.now
    pool_price_per_share = gauge.pool.getRate(block_identifier=now)
    pool_token_price = magic.get_price(gauge.lp_token, block=now)
    performance_fee, management_fee, keep_bal = get_vault_fees(vault, block=now)

    apr_data = get_current_aura_apr(
        vault, gauge,
        pool_price_per_share, 
        pool_token_price,
        block=now
    )

    gross_apr = apr_data.gross_apr * apr_data.debt_ratio

    net_booster_apr = apr_data.net_apr * (1 - performance_fee) - management_fee
    net_booster_apy = (1 + (net_booster_apr / COMPOUNDING)) ** COMPOUNDING - 1
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
        "extra_rewards_apr": apr_data.extra_rewards_apr,
        "aura_gross_apr": apr_data.gross_apr,
        "aura_net_apr": apr_data.net_apr,
        "booster_net_apr": net_booster_apr,
    }

    blocks = ApyBlocks(
        samples.now, 
        samples.week_ago, 
        samples.month_ago, 
        vault.reports[0].block_number
    )

    return Apy('aura', gross_apr, net_apy, fees, composite=composite, blocks=blocks)

def get_current_aura_apr(
        vault, gauge, 
        pool_price_per_share, 
        pool_token_price,
        block=None
) -> AuraAprData:
    """Calculate the current APR as opposed to projected APR like we do with CRV-CVX"""
    strategy = vault.strategies[0].strategy
    debt_ratio = get_debt_ratio(vault, strategy)
    booster = contract(addresses[chain.id]['booster'])
    booster_fee = get_booster_fee(booster, block)
    booster_boost = gauge.calculate_boost(MAX_BOOST, addresses[chain.id]['booster_voter'], block)
    extra_rewards_apr = get_booster_reward_apr(strategy, booster, pool_price_per_share, pool_token_price, block)

    bal_price = magic.get_price(addresses[chain.id]['bal'], block=block)
    aura_price = magic.get_price(addresses[chain.id]['aura'], block=block)

    rewards = contract(strategy.rewardsContract())
    rewards_tvl = pool_token_price * rewards.totalSupply() / 10**rewards.decimals()

    bal_rewards_per_year = (rewards.rewardRate()/10**rewards.decimals()) * SECONDS_PER_YEAR
    bal_rewards_per_year_usd =  bal_rewards_per_year * bal_price
    bal_rewards_apr = bal_rewards_per_year_usd / rewards_tvl

    aura_emission_rate = get_aura_emission_rate(block)
    aura_rewards_per_year = bal_rewards_per_year * aura_emission_rate
    aura_rewards_per_year_usd = aura_rewards_per_year * aura_price
    aura_rewards_apr = aura_rewards_per_year_usd / rewards_tvl

    gross_apr = bal_rewards_apr + aura_rewards_apr + extra_rewards_apr
    net_apr = (bal_rewards_apr + aura_rewards_apr) * (1 - booster_fee) + extra_rewards_apr

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    return AuraAprData(
        booster_boost,
        bal_rewards_apr,
        aura_rewards_apr,
        extra_rewards_apr,
        gross_apr,
        net_apr,
        debt_ratio
    )

def get_vault_fees(vault, block=None):
    if vault:
        vault_contract = vault.vault
        if len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, 'keepBAL'):
            keep_bal = vault.strategies[0].strategy.keepBAL(block_identifier=block) / 1e4
        else:
            keep_bal = 0
        performance = vault_contract.performanceFee(block_identifier=block) / 1e4 if hasattr(vault_contract, "performanceFee") else 0
        management = vault_contract.managementFee(block_identifier=block) / 1e4 if hasattr(vault_contract, "managementFee") else 0

    else:
        # used for APY calculation previews
        performance = 0.1
        management = 0
        keep_bal = 0
    
    return performance, management, keep_bal

def get_aura_emission_rate(block=None) -> float:
    aura = contract(addresses[chain.id]['aura'])
    initial_mint = aura.INIT_MINT_AMOUNT()
    supply = aura.totalSupply(block_identifier=block)
    max_supply = initial_mint + aura.EMISSIONS_MAX_SUPPLY()

    if supply <= max_supply:
        total_cliffs = aura.totalCliffs()
        minter_minted = get_aura_minter_minted(block)
        reduction_per_cliff = aura.reductionPerCliff()
        current_cliff = (supply - initial_mint - minter_minted) / reduction_per_cliff
        reduction =  2.5 * (total_cliffs - current_cliff) + 700

        if os.getenv('DEBUG', None):
            logger.info(pformat(Debug().collect_variables(locals())))

        return reduction / total_cliffs
    else:
        if os.getenv('DEBUG', None):
            logger.info(pformat(Debug().collect_variables(locals())))

        return 0

def get_aura_minter_minted(block=None) -> float:
    """According to Aura's docs you should use the minterMinted field when calculating the
    current aura emission rate. The minterMinted field is private in the contract though!?
    So get it by storage slot"""
    return web3.eth.get_storage_at(addresses[chain.id]['aura'], 7, block_identifier=block)

def get_debt_ratio(vault, strategy) -> float:
    return vault.vault.strategies(strategy)[2] / 1e4
