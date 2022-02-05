import logging
from time import time

from brownie import ZERO_ADDRESS, Contract, chain, interface
from semantic_version import Version
from yearn.apy.common import (SECONDS_PER_YEAR, Apy, ApyError, ApyFees,
                              ApySamples, SharePricePoint, calculate_roi, get_samples, StrategyApy, try_composite as crv_composite)
from yearn.apy.curve.rewards import rewards
from yearn.networks import Network
from yearn.prices.curve import curve
from yearn.prices.magic import get_price
from yearn.utils import get_block_timestamp, contract as get_contract

logger = logging.getLogger(__name__)

addresses = {
    Network.Mainnet: {
        'cvx': '0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B',
        'yearn_voter_proxy': '0xF147b8125d2ef93FB6965Db97D6746952a133934',
        'convex_voter_proxy': '0x989AEb4d175e16225E39E87d0D97A3360524AD80',
        'convex_booster': '0xF403C135812408BFbE8713b5A23a04b3D48AAE31',
        'rkp3r_rewards': '0xEdB67Ee1B171c4eC66E6c10EC43EDBbA20FaE8e9',
        'kp3r': '0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44',
    }
}

MAX_BOOST = 2.5
PER_MAX_BOOST = 1.0 / MAX_BOOST

# calculate our forward-looking APY per strategy for curve and convex
def curve_strategy_apy(strategy) -> StrategyApy:
    print("Here's the start")
    lp_token = strategy.strategy.want()
    vault_contract = strategy.vault.vault
    strategy_contract = strategy.strategy
    samples = get_samples()
    
    # calculate our curve pool APY, needed for curve and convex
    pool_address = curve.get_pool(lp_token)
    pool = get_contract(pool_address)
    block = samples.now
    pool_price = pool.get_virtual_price(block_identifier=block)

    price_per_share = pool.get_virtual_price
    now_price = price_per_share(block_identifier=samples.now)
    try:
        week_ago_price = price_per_share(block_identifier=samples.week_ago)
    except ValueError:
        raise ApyError("crv", "insufficient data")

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)

    pool_apr = calculate_roi(now_point, week_ago_point)
    pool_apy = (((pool_apr / 365) + 1) ** 365) - 1

    # this is for curve strategy calcs
    gauge_address = curve.get_gauge(pool_address)
    if gauge_address is None:
        raise ApyError("crv", "no gauge")

    gauge = get_contract(gauge_address)

    try:
        controller = gauge.controller()
        controller = get_contract(controller)
    except:
        # newer gauges do not have a 'controller' method
        controller = curve.gauge_controller

    gauge_weight = controller.gauge_relative_weight.call(gauge_address, block_identifier=block) 
    gauge_working_supply = gauge.working_supply(block_identifier=block)
    if gauge_working_supply == 0:
        raise ApyError("crv", "gauge working supply is zero")

    gauge_inflation_rate = gauge.inflation_rate(block_identifier=block)
    base_asset_price = get_price(lp_token, block=block) or 1
    crv_price = get_price(curve.crv, block=block)

    yearn_voter = addresses[chain.id]['yearn_voter_proxy']
    y_working_balance = gauge.working_balances(yearn_voter, block_identifier=block)
    y_gauge_balance = gauge.balanceOf(yearn_voter, block_identifier=block)

    base_apr = (
        gauge_inflation_rate
        * gauge_weight
        * (SECONDS_PER_YEAR / gauge_working_supply)
        * (PER_MAX_BOOST / pool_price)
        * crv_price
    ) / base_asset_price

    if y_gauge_balance > 0:
        boost = y_working_balance / (PER_MAX_BOOST * y_gauge_balance) or 1
    else:
        boost = MAX_BOOST

    # TODO: come up with cleaner way to deal with these new gauge rewards
    reward_apr = 0
    current_time = time() if block is None else get_block_timestamp(block)
    if hasattr(gauge, "reward_contract"):
        reward_address = gauge.reward_contract()
        if reward_address != ZERO_ADDRESS:
            reward_apr = rewards(reward_address, pool_price, base_asset_price, block=block)
    elif hasattr(gauge, "reward_data"): # this is how new gauges, starting with MIM, show rewards
        # get our token
        for i in range(gauge.reward_count()):
            gauge_reward_token = gauge.reward_tokens(i)
            if gauge_reward_token in [ZERO_ADDRESS]:
                print("no reward token in this spot")
                break
            reward_data = gauge.reward_data(gauge_reward_token)
            rate = reward_data['rate']
            period_finish = reward_data['period_finish']
            total_supply = gauge.totalSupply()
            token_price = 0
            # rKP3R tokens are worth a discounted rate based on the option
            if gauge_reward_token == addresses[chain.id]['rkp3r_rewards']:
                rKP3R_contract = interface.rKP3R(gauge_reward_token)
                discount = rKP3R_contract.discount(block_identifier=block)
                token_price = get_price(addresses[chain.id]['kp3r'], block=block) * (100 - discount) / 100
            else:
                token_price = get_price(gauge_reward_token, block=block)
            if period_finish < current_time:
                reward_apr += 0
            else:
                reward_apr += (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / ((pool_price / 1e18) * (total_supply / 1e18) * base_asset_price)
    
    # get our keepCRV
    if hasattr(strategy_contract, "keepCRV"):
        keep_crv = strategy_contract.keepCRV(block_identifier=block) / 1e4
    elif hasattr(strategy_contract, "keepCrvPercent"):
        keep_crv = strategy_contract.keepCrvPercent(block_identifier=block) / 1e4
    else:
        keep_crv = 0
                
    # calculate our curve APR
    curve_reward_apr = reward_apr
    boosted_apr = base_apr * boost
    gross_apr = boosted_apr + reward_apr
    crv_apr_minus_keep_crv = base_apr * boost * (1 - keep_crv)

    # assume we are compounding every week on mainnet, daily on sidechains
    if chain.id == 1:
        compounding = 52
    else:
        compounding = 365.25

    # add in our fees
    strategy_performance_fee = vault_contract.strategies(strategy_contract)['performanceFee'] / 1e4
    vault_performance_fee = (vault_contract.performanceFee(block_identifier=block)) / 1e4 if hasattr(vault_contract, "performanceFee") else 0
    performance = vault_performance_fee + strategy_performance_fee
    management = vault_contract.managementFee(block_identifier=block) / 1e4 if hasattr(vault_contract, "managementFee") else 0

    # calculate our net apy
    crv_net_apr = (crv_apr_minus_keep_crv + reward_apr) * (1 - performance) - management
    crv_net_farmed_apy = (1 + (crv_net_apr / compounding)) ** compounding - 1
    net_apy = ((1 + crv_net_farmed_apy) * (1 + pool_apy)) - 1
        
    strategy_composite = {
            "boost": boost,
            "pool_apy": pool_apy,
            "base_apr": base_apr,
            "boosted_apr": boosted_apr,
            "rewards_apr": curve_reward_apr,
            "cvx_apr": 0,
    }

    # as long as we have a convex strategy, calculate our convex APY
    if hasattr(strategy_contract, "pid"):
        pid = strategy_contract.pid()   
        convex_voter = addresses[chain.id]['convex_voter_proxy']
        cvx_working_balance = gauge.working_balances(convex_voter, block_identifier=block)
        cvx_gauge_balance = gauge.balanceOf(convex_voter, block_identifier=block)
        
        if cvx_gauge_balance > 0:
            cvx_boost = cvx_working_balance / (PER_MAX_BOOST * cvx_gauge_balance) or 1
        else:
            cvx_boost = MAX_BOOST
        
        cvx_booster = get_contract(addresses[chain.id]['convex_booster'])
        cvx_lock_incentive = cvx_booster.lockIncentive(block_identifier=block)
        cvx_staker_incentive = cvx_booster.stakerIncentive(block_identifier=block)
        cvx_earmark_incentive = cvx_booster.earmarkIncentive(block_identifier=block)
        cvx_platform_fee = cvx_booster.platformFee(block_identifier=block)
        cvx_fee = (cvx_lock_incentive + cvx_staker_incentive + cvx_earmark_incentive + cvx_platform_fee) / 1e4
        cvx_keep_crv = strategy_contract.keepCRV(block_identifier=block) / 1e4
        
        # pull data from convex's virtual rewards contracts to get bonus rewards, so far only CVX
        rewards_contract = get_contract(cvx_booster.poolInfo(pid)["crvRewards"])
        rewards_length = rewards_contract.extraRewardsLength()
        if rewards_length > 0:
            reward_apr = 0 # reset our rewards apr if we're calculating it via convex
            for x in range(rewards_length):
                print("This is our x value:", x)
                virtual_rewards_pool = get_contract(rewards_contract.extraRewards(x))
                 # do this for all assets, which will duplicate much of the curve info but we don't want to miss anything
                if virtual_rewards_pool.periodFinish() > current_time:
                    reward_apr += (virtual_rewards_pool.rewardRate() * SECONDS_PER_YEAR * get_price(virtual_rewards_pool.rewardToken(), block=block)) / (base_asset_price * (pool_price / 1e18) * virtual_rewards_pool.totalSupply())

        # this is some black magic based on CVX emissions from the token contract
        total_cliff = 1e3
        max_supply = 1e2 * 1e6 * 1e18
        reduction_per_cliff = 1e23
        cvx = get_contract(addresses[chain.id]['cvx'])
        supply = cvx.totalSupply(block_identifier=block)
        cliff = supply / reduction_per_cliff
        
        # convert our CVX yield into CRV to more easily calculate APR
        if supply <= max_supply:
            reduction = total_cliff - cliff
            cvx_minted_as_crv = reduction / total_cliff
            cvx_price = get_price(cvx, block=block)
            converted_cvx = cvx_price / crv_price
            cvx_printed_as_crv = cvx_minted_as_crv * converted_cvx
        else:
            cvx_printed_as_crv = 0
        
        gross_apr = ((1 - cvx_fee) * cvx_boost * base_apr) * (1 + cvx_printed_as_crv) + reward_apr
        cvx_boosted_apr = (1 - cvx_fee) * cvx_boost * base_apr
        cvx_apr_minus_keep_crv = ((1 - cvx_fee) * cvx_boost * base_apr) * ((1 - keep_crv) + cvx_printed_as_crv)
        
        # cvx_apr is how much extra yield convex adds with cvx printing alone, directly for CRV and in virtual rewards pools
        cvx_apr = gross_apr - cvx_boosted_apr - curve_reward_apr
        
        # add in our fees
        strategy_performance_fee = vault_contract.strategies(strategy_contract)['performanceFee'] / 1e4
        vault_performance_fee = (vault_contract.performanceFee(block_identifier=block)) / 1e4 if hasattr(vault_contract, "performanceFee") else 0
        performance = vault_performance_fee + strategy_performance_fee
        management = vault_contract.managementFee(block_identifier=block) / 1e4 if hasattr(vault_contract, "managementFee") else 0
        
        # calculate our net apy
        cvx_net_apr = (cvx_apr_minus_keep_crv + reward_apr) * (1 - performance) - management
        cvx_net_farmed_apy = (1 + (cvx_net_apr / compounding)) ** compounding - 1
        net_apy = ((1 + cvx_net_farmed_apy) * (1 + pool_apy)) - 1
        
        strategy_composite = {
            "boost": cvx_boost,
            "pool_apy": pool_apy,
            "base_apr": base_apr,
            "boosted_apr": cvx_boosted_apr,
            "rewards_apr": reward_apr,
            "cvx_apr": cvx_apr,
        }
        
        # 0.3.5+ should never be < 0% because of management
        if net_apy < 0 and Version(vault_contract.api_version()) >= Version("0.3.5"):
            net_apy = 0
        
        fees = ApyFees(performance=performance, management=management, keep_crv=keep_crv)
        print("end of convex")
        
        if crv_composite:
            return StrategyApy("convex", gross_apr, net_apy, fees, composite=strategy_composite)
        else:
            return StrategyApy("convex", gross_apr, net_apy, fees)     
    else:
        print("not a convex strategy")

    # 0.3.5+ should never be < 0% because of management
    if net_apy < 0 and Version(vault_contract.api_version()) >= Version("0.3.5"):
        net_apy = 0

    fees = ApyFees(performance=performance, management=management, keep_crv=keep_crv)
    if crv_composite:
        return StrategyApy("curve", gross_apr, net_apy, fees, composite=strategy_composite)
    else:
        return StrategyApy("curve", gross_apr, net_apy, fees)