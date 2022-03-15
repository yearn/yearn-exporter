from dataclasses import dataclass
import logging
from time import time

from brownie import ZERO_ADDRESS, chain, interface
from semantic_version import Version
from yearn.apy.common import (SECONDS_PER_YEAR, Apy, ApyError, ApyFees,
                              ApySamples, SharePricePoint, calculate_roi)
from yearn.apy.curve.rewards import rewards
from yearn.networks import Network
from yearn.prices import magic
from yearn.prices.curve import curve
from yearn.utils import contract, get_block_timestamp


@dataclass 
class ConvexDetailedApyData:
    cvx_apr: float = 0
    cvx_apr_minus_keep_crv: float = 0
    cvx_keep_crv: float = 0
    cvx_debt_ratio: float = 0
    convex_reward_apr: float = 0


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

COMPOUNDING = 52
MAX_BOOST = 2.5
PER_MAX_BOOST = 1.0 / MAX_BOOST


def simple(vault, samples: ApySamples) -> Apy:
    lp_token = vault.token.address

    pool_address = curve.get_pool(lp_token)

    gauge_address = curve.get_gauge(pool_address)

    if gauge_address is None:
        raise ApyError("crv", "no gauge")

    gauge = contract(gauge_address)

    try:
        controller = gauge.controller()
        controller = contract(controller)
    except:
        # newer gauges do not have a 'controller' method
        controller = curve.gauge_controller

    block = samples.now
    gauge_weight = controller.gauge_relative_weight.call(gauge_address, block_identifier=block) 
    gauge_working_supply = gauge.working_supply(block_identifier=block)
    if gauge_working_supply == 0:
        raise ApyError("crv", "gauge working supply is zero")

    gauge_inflation_rate = gauge.inflation_rate(block_identifier=block)
    pool = contract(pool_address)
    pool_price = pool.get_virtual_price(block_identifier=block)

    base_asset_price = magic.get_price(lp_token, block=block) or 1

    crv_price = magic.get_price(curve.crv, block=block)

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

    # FIXME: The HBTC v1 vault is currently still earning yield, but it is no longer boosted.
    if vault.vault.address == "0x46AFc2dfBd1ea0c0760CAD8262A5838e803A37e5":
        boost = 1

    # TODO: come up with cleaner way to deal with these new gauge rewards
    reward_apr = 0
    if hasattr(gauge, "reward_contract"):
        reward_address = gauge.reward_contract()
        if reward_address != ZERO_ADDRESS:
            reward_apr = rewards(reward_address, pool_price, base_asset_price, block=block)
    elif hasattr(gauge, "reward_data"): # this is how new gauges, starting with MIM, show rewards
        # get our token
        # TODO: consider adding for loop with [gauge.reward_tokens(i) for i in range(gauge.reward_count())] for multiple rewards tokens
        gauge_reward_token = gauge.reward_tokens(0)
        if gauge_reward_token in [ZERO_ADDRESS]:
            print("no reward token")
        else:
            reward_data = gauge.reward_data(gauge_reward_token)
            rate = reward_data['rate']
            period_finish = reward_data['period_finish']
            total_supply = gauge.totalSupply()
            token_price = 0
            if gauge_reward_token == addresses[chain.id]['rkp3r_rewards']:
                rKP3R_contract = interface.rKP3R(gauge_reward_token)
                discount = rKP3R_contract.discount(block_identifier=block)
                token_price = magic.get_price(addresses[chain.id]['kp3r'], block=block) * (100 - discount) / 100
            else:
                token_price = magic.get_price(gauge_reward_token, block=block)
            current_time = time() if block is None else get_block_timestamp(block)
            if period_finish < current_time:
                reward_apr = 0
            else:
                reward_apr = (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / ((pool_price / 1e18) * (total_supply / 1e18) * base_asset_price)
    else:
        reward_apr = 0

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

    # FIXME: crvANKR's pool apy going crazy
    if vault.vault.address == "0xE625F5923303f1CE7A43ACFEFd11fd12f30DbcA4":
        pool_apy = 0

    # prevent circular import for partners calculations
    from yearn.v2.vaults import Vault as VaultV2

    if isinstance(vault, VaultV2):
        vault_contract = vault.vault
        if len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, "keepCRV"):
            crv_keep_crv = vault.strategies[0].strategy.keepCRV(block_identifier=block) / 1e4
        elif len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, "keepCrvPercent"):
            crv_keep_crv = vault.strategies[0].strategy.keepCrvPercent(block_identifier=block) / 1e4
        else:
            crv_keep_crv = 0
        performance = (vault_contract.performanceFee(block_identifier=block) * 2) / 1e4 if hasattr(vault_contract, "performanceFee") else 0
        management = vault_contract.managementFee(block_identifier=block) / 1e4 if hasattr(vault_contract, "managementFee") else 0
    else:
        strategy = vault.strategy
        strategist_performance = strategy.performanceFee(block_identifier=block) if hasattr(strategy, "performanceFee") else 0
        strategist_reward = strategy.strategistReward(block_identifier=block) if hasattr(strategy, "strategistReward") else 0
        treasury = strategy.treasuryFee(block_identifier=block) if hasattr(strategy, "treasuryFee") else 0
        crv_keep_crv = strategy.keepCRV(block_identifier=block) / 1e4 if hasattr(strategy, "keepCRV") else 0

        performance = (strategist_reward + strategist_performance + treasury) / 1e4
        management = 0
    
    # if the vault consists of only a convex strategy then return 
    # specialized apy calculations for convex
    if _ConvexVault.is_convex_vault(vault):
        cvx_strategy = vault.strategies[0].strategy
        cvx_vault = _ConvexVault(cvx_strategy, vault, gauge)
        return cvx_vault.apy(base_asset_price, pool_price, base_apr, pool_apy, management, performance)

    # if the vault has two strategies then the first is curve and the second is convex
    if isinstance(vault, VaultV2) and len(vault.strategies) == 2: # this vault has curve and convex
        crv_strategy = vault.strategies[0].strategy
        cvx_strategy = vault.strategies[1].strategy
        cvx_vault = _ConvexVault(cvx_strategy, vault, gauge)
        crv_debt_ratio = vault.vault.strategies(crv_strategy)[2] / 1e4
        cvx_apy_data = cvx_vault.get_detailed_apy_data(base_asset_price, pool_price, base_apr)
    else:
        # otherwise there's no convex/curve strategy data to use 
        cvx_apy_data = ConvexDetailedApyData()
        crv_debt_ratio = 0

    crv_apr = base_apr * boost + reward_apr
    crv_apr_minus_keep_crv = base_apr * boost * (1 - crv_keep_crv)

    gross_apr = (1 + (crv_apr * crv_debt_ratio + cvx_apy_data.cvx_apr * cvx_apy_data.cvx_debt_ratio)) * (1 + pool_apy) - 1

    cvx_net_apr = (cvx_apy_data.cvx_apr_minus_keep_crv + cvx_apy_data.convex_reward_apr) * (1 - performance) - management
    cvx_net_farmed_apy = (1 + (cvx_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    cvx_net_apy = ((1 + cvx_net_farmed_apy) * (1 + pool_apy)) - 1

    crv_net_apr = (crv_apr_minus_keep_crv + reward_apr) * (1 - performance) - management
    crv_net_farmed_apy = (1 + (crv_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    crv_net_apy = ((1 + crv_net_farmed_apy) * (1 + pool_apy)) - 1

    net_apy = crv_net_apy * crv_debt_ratio + cvx_net_apy * cvx_apy_data.cvx_debt_ratio

    # 0.3.5+ should never be < 0% because of management
    if isinstance(vault, VaultV2) and net_apy < 0 and Version(vault.api_version) >= Version("0.3.5"):
        net_apy = 0

    fees = ApyFees(performance=performance, management=management, keep_crv=crv_keep_crv, cvx_keep_crv=cvx_apy_data.cvx_keep_crv)
    composite = {
        "boost": boost,
        "pool_apy": pool_apy,
        "boosted_apr": crv_apr,
        "base_apr": base_apr,
        "cvx_apr": cvx_apy_data.cvx_apr,
        "rewards_apr": reward_apr,
    }

    return Apy("crv", gross_apr, net_apy, fees, composite=composite)

class _ConvexVault:
    def __init__(self, cvx_strategy, vault, gauge, block=None) -> None:
        self._cvx_strategy = cvx_strategy
        self.block = block
        self.vault = vault
        self.gauge = gauge

    @staticmethod
    def is_convex_vault(vault) -> bool:
        """Determines whether the passed in vault is a Convex vault
        i.e. it only has one strategy that's based on farming Convex.
        """
        # prevent circular import for partners calculations
        from yearn.v2.vaults import Vault as VaultV2
        if not isinstance(vault, VaultV2):
            return False 

        return len(vault.strategies) == 1 and "convex" in vault.strategies[0].name.lower()

    def apy(self, base_asset_price, pool_price, base_apr, pool_apy: float, management_fee: float, performance_fee: float) -> Apy:
        """The standard APY data."""
        apy_data = self.get_detailed_apy_data(base_asset_price, pool_price, base_apr)
        gross_apr = (1 + (apy_data.cvx_apr * apy_data.cvx_debt_ratio)) * (1 + pool_apy) - 1

        cvx_net_apr = (apy_data.cvx_apr_minus_keep_crv + apy_data.convex_reward_apr) * (1 - performance_fee) - management_fee
        cvx_net_farmed_apy = (1 + (cvx_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
        cvx_net_apy = ((1 + cvx_net_farmed_apy) * (1 + pool_apy)) - 1

        fees = ApyFees(performance=performance_fee, management=management_fee, cvx_keep_crv=apy_data.cvx_keep_crv)
        return Apy("convex", gross_apr, cvx_net_apy, fees)

    def get_detailed_apy_data(self, base_asset_price, pool_price, base_apr) -> ConvexDetailedApyData:
        """Detailed data about the apy."""
        cvx_keep_crv = self._cvx_strategy.keepCRV(block_identifier=self.block) / 1e4

        cvx_booster = contract(addresses[chain.id]['convex_booster'])
        cvx_fee = self._get_convex_fee(cvx_booster, self.block)
        convex_reward_apr = self._get_reward_apr(self._cvx_strategy, cvx_booster, base_asset_price, pool_price, self.block)

        cvx_boost = self._get_cvx_boost()
        cvx_printed_as_crv = self._get_cvx_emissions_printed_as_crv()
        cvx_apr = ((1 - cvx_fee) * cvx_boost * base_apr) * (1 + cvx_printed_as_crv) + convex_reward_apr
        cvx_apr_minus_keep_crv = ((1 - cvx_fee) * cvx_boost * base_apr) * ((1 - cvx_keep_crv) + cvx_printed_as_crv)
        
        return ConvexDetailedApyData(cvx_apr, cvx_apr_minus_keep_crv, cvx_keep_crv, self._debt_ratio, convex_reward_apr)

    def _get_cvx_emissions_printed_as_crv(self) -> float:
        """The amount of CVX emissions at the current block, in terms of CRV."""
        crv_price = get_price(curve.crv, block=self.block)
        total_cliff = 1e3
        max_supply = 1e2 * 1e6 * 1e18 # ?
        reduction_per_cliff = 1e23
        cvx = contract(addresses[chain.id]['cvx'])
        supply = cvx.totalSupply(block_identifier=self.block)
        cliff = supply / reduction_per_cliff
        if supply <= max_supply:
            reduction = total_cliff - cliff
            cvx_minted_as_crv = reduction / total_cliff
            cvx_price = get_price(cvx, block=self.block)
            converted_cvx = cvx_price / crv_price
            return cvx_minted_as_crv * converted_cvx
        else:
            return 0

    def _get_cvx_boost(self) -> float:
        """The amount of boost being applied to this pool by Convex."""
        convex_voter = addresses[chain.id]['convex_voter_proxy']
        cvx_working_balance = self.gauge.working_balances(convex_voter, block_identifier=self.block)
        cvx_gauge_balance = self.gauge.balanceOf(convex_voter, block_identifier=self.block)

        if cvx_gauge_balance > 0:
            return cvx_working_balance / (PER_MAX_BOOST * cvx_gauge_balance) or 1
        else:
            return MAX_BOOST

    def _get_reward_apr(self, cvx_strategy, cvx_booster, base_asset_price, pool_price, block=None) -> float:
        """The cumulative apr of all extra tokens that are emitted by depositing 
        to Convex, assuming that they will be sold for profit.
        """
        # pull data from convex's virtual rewards contracts to get bonus rewards
        pid = cvx_strategy.pid()
        rewards_contract = contract(cvx_booster.poolInfo(pid)["crvRewards"])
        rewards_length = rewards_contract.extraRewardsLength()
        current_time = time() if block is None else get_block_timestamp(block)
        if rewards_length > 0:
            convex_reward_apr = 0 # reset our rewards apr if we're calculating it via convex
            for x in range(rewards_length):
                virtual_rewards_pool = contract(rewards_contract.extraRewards(x))
                    # do this for all assets, which will duplicate much of the curve info but we don't want to miss anything
                if virtual_rewards_pool.periodFinish() > current_time:
                    convex_reward_apr += (virtual_rewards_pool.rewardRate() * SECONDS_PER_YEAR * magic.get_price(virtual_rewards_pool.rewardToken(), block=block)) / (base_asset_price * (pool_price / 1e18) * virtual_rewards_pool.totalSupply())

        return convex_reward_apr

    def _get_convex_fee(self, cvx_booster, block=None) -> float:
        """The fee % that Convex charges."""
        cvx_lock_incentive = cvx_booster.lockIncentive(block_identifier=block)
        cvx_staker_incentive = cvx_booster.stakerIncentive(block_identifier=block)
        cvx_earmark_incentive = cvx_booster.earmarkIncentive(block_identifier=block)
        cvx_platform_fee = cvx_booster.platformFee(block_identifier=block)
        return (cvx_lock_incentive + cvx_staker_incentive + cvx_earmark_incentive + cvx_platform_fee) / 1e4

    @property
    def _debt_ratio(self) -> float:
        """The debt ratio of the Convex strategy."""
        return self.vault.vault.strategies(self._cvx_strategy)[2] / 1e4
