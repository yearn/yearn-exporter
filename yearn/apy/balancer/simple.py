import logging
import os
from pprint import pformat

from brownie import chain
from dataclasses import dataclass
from semantic_version import Version

from yearn.apy.common import Apy, ApyBlocks, ApyError, ApyFees, ApySamples, calculate_pool_apy
from yearn.apy.booster import get_booster_fee, get_booster_reward_apr
from yearn.apy.gauge import Gauge
from yearn.debug import Debug
from yearn.networks import Network
from yearn.prices import magic
from yearn.utils import contract


logger = logging.getLogger(__name__)

@dataclass
class AuraApyData:
    boost: float = 0
    apr: float = 0
    apr_minus_keep: float = 0
    keep: float = 0
    debt_ratio: float = 0
    reward_apr: float = 0

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

    return calculate_simple(
        vault,
        Gauge(pool.address, pool, gauge, gauge_weight, gauge_inflation_rate, gauge_working_supply),
        samples
    )

def calculate_simple(vault, gauge: Gauge, samples: ApySamples) -> Apy:
    now = samples.now
    pool_price_per_share = gauge.pool.getRate(block_identifier=now)
    pool_token_price = magic.get_price(gauge.lp_token, block=now)
    bal_price = magic.get_price(addresses[chain.id]['bal'], block=now)
    gauge_base_apr = gauge.calculate_base_apr(MAX_BOOST, bal_price, pool_price_per_share, pool_token_price)
    _, pool_apy = calculate_pool_apy(vault, gauge.pool.getRate, samples)
    pool_rewards_apr = gauge.calculate_rewards_apr(pool_price_per_share, pool_token_price, block=now)

    if vault:
        return calculate_simple_aura_apy(
            vault, gauge, 
            pool_rewards_apr,
            pool_price_per_share, 
            pool_token_price, 
            gauge_base_apr, 
            pool_apy,
            samples
        )

    # currently just for apy preview, mirrors corresponding code from crv-cvx calculation
    # assumes a 2 strategy design, one for balancer with 100% dr, one for aura with 0 dr
    performance_fee, management_fee, keep_bal = get_vault_fees(vault, block=now)
    voter_boost = gauge.calculate_boost(MAX_BOOST, addresses[chain.id]['voter'], block=now)
    aura_apy_data = AuraApyData(debt_ratio=0)
    bal_debt_ratio = 1

    bal_apr = gauge_base_apr * voter_boost + pool_rewards_apr
    bal_apr_minus_keep_bal = gauge_base_apr * voter_boost * (1 - keep_bal)

    gross_apr = (1 + (bal_apr * bal_debt_ratio + aura_apy_data.apr * aura_apy_data.debt_ratio)) * (1 + pool_apy) - 1

    aura_net_apr = (aura_apy_data.apr_minus_keep + aura_apy_data.reward_apr) * (1 - performance_fee) - management_fee
    aura_net_farmed_apy = (1 + (aura_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    aura_net_apy = ((1 + aura_net_farmed_apy) * (1 + pool_apy)) - 1

    bal_net_apr = (bal_apr_minus_keep_bal + pool_rewards_apr) * (1 - performance_fee) - management_fee
    bal_net_farmed_apy = (1 + (bal_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    bal_net_apy = ((1 + bal_net_farmed_apy) * (1 + pool_apy)) - 1

    net_apy = bal_net_apy * bal_debt_ratio + aura_net_apy * aura_apy_data.debt_ratio
  
    boost = voter_boost * bal_debt_ratio

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault.api_version) >= Version('0.3.5'): 
        net_apy = 0

    fees = ApyFees(
        performance=performance_fee,
        management=management_fee,
        keep_bal=keep_bal,
        aura_keep_bal=aura_apy_data.keep
    )

    composite = {
        "boost": boost,
        "pool_apy": pool_apy,
        "boosted_apr": bal_apr,
        "base_apr": gauge_base_apr,
        "aura_apr": aura_apy_data.aura_apr,
        "rewards_apr": pool_rewards_apr
    }

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    return Apy('bal', gross_apr, net_apy, fees, composite=composite)

def calculate_simple_aura_apy(
        vault, gauge, 
        pool_rewards_apr,
        pool_price_per_share, 
        pool_token_price, 
        gauge_base_apr, 
        pool_apy,
        samples
) -> Apy:
    now = samples.now
    performance_fee, management_fee, keep_bal = get_vault_fees(vault, block=now)

    apy_data = get_aura_apy_data(
        vault, gauge,
        pool_price_per_share, 
        pool_token_price, 
        gauge_base_apr,
        keep_bal,
        block=now
    )

    gross_apr = (1 + (apy_data.apr * apy_data.debt_ratio)) * (1 + pool_apy) - 1

    net_booster_apr = (apy_data.apr_minus_keep + apy_data.reward_apr) * (1 - performance_fee) - management_fee
    net_booster_apy = (1 + (net_booster_apr / COMPOUNDING)) ** COMPOUNDING - 1
    net_apy = ((1 + net_booster_apy) * (1 + pool_apy)) - 1

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault.api_version) >= Version('0.3.5'): 
        net_apy = 0

    fees = ApyFees(
        performance=performance_fee, 
        management=management_fee, 
        keep_crv=keep_bal, 
        cvx_keep_crv=apy_data.keep
    )

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    composite = {
        "boost": apy_data.boost,
        "pool_apy": pool_apy,
        "boosted_apr": net_booster_apr,
        "base_apr": gauge_base_apr,
        "aura_apr": apy_data.apr,
        "rewards_apr": pool_rewards_apr
    }
    blocks = ApyBlocks(samples.now, samples.week_ago, samples.month_ago, vault.reports[0].block_number)
    return Apy('aura', gross_apr, net_apy, fees, composite=composite, blocks=blocks)

def get_aura_apy_data(
        vault, gauge, 
        pool_price_per_share, 
        pool_token_price, 
        gauge_base_apr,
        keep_bal,
        block=None
) -> AuraApyData:
    strategy = vault.strategies[0].strategy
    debt_ratio = get_debt_ratio(vault, strategy)
    booster = contract(addresses[chain.id]['booster'])
    booster_fee = get_booster_fee(booster, block)
    booster_reward_apr = get_booster_reward_apr(strategy, booster, pool_price_per_share, pool_token_price, block)
    booster_boost = gauge.calculate_boost(MAX_BOOST, addresses[chain.id]['booster_voter'], block)
    emitted_aura_priced_in_bal = get_emitted_aura_priced_in_bal(block)

    booster_apr = (
        ((1 - booster_fee) * booster_boost * gauge_base_apr) 
        * (1 + emitted_aura_priced_in_bal) 
        + booster_reward_apr
    )

    booster_apr_minus_keep = (
        ((1 - booster_fee) * booster_boost * gauge_base_apr) 
        * ((1 - keep_bal) + emitted_aura_priced_in_bal)
    )

    if os.getenv('DEBUG', None):
        logger.info(pformat(Debug().collect_variables(locals())))

    return AuraApyData(
        booster_boost,
        booster_apr,
        booster_apr_minus_keep,
        keep_bal,
        debt_ratio,
        booster_reward_apr
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

def get_emitted_aura_priced_in_bal(block=None) -> float:
    """AURA emissions converted priced in BAL to ease calculation of total APY."""
    bal_price = magic.get_price(addresses[chain.id]['bal'], block=block)
    aura = contract(addresses[chain.id]['aura'])
    total_cliffs = aura.totalCliffs()
    max_supply = aura.EMISSIONS_MAX_SUPPLY()
    reduction_per_cliff = aura.reductionPerCliff()
    supply = aura.totalSupply(block_identifier=block)
    current_cliff = supply / reduction_per_cliff
    if supply <= max_supply:
        reduction = total_cliffs - current_cliff
        minted = reduction / total_cliffs
        aura_price = magic.get_price(aura, block=block)
        return minted * (aura_price / bal_price)
    else:
        return 0

def get_debt_ratio(vault, strategy) -> float:
    return vault.vault.strategies(strategy)[2] / 1e4
