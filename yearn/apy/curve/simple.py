import asyncio
import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pprint import pformat
from time import time

import requests
from brownie import ZERO_ADDRESS, chain, interface
from dank_mids.brownie_patch import patch_contract
from eth_abi import encode_single
from eth_utils import function_signature_to_4byte_selector as fourbyte
from semantic_version import Version
from y import Contract, Network
from y.prices import magic
from y.prices.stable_swap.curve import curve as y_curve
from y.time import get_block_timestamp_async
from y.utils.dank_mids import dank_w3

from yearn.apy.common import (SECONDS_PER_WEEK, SECONDS_PER_YEAR, Apy,
                              ApyError, ApyFees, ApySamples, SharePricePoint,
                              calculate_roi)
from yearn.apy.curve.rewards import rewards
from yearn.apy.gauge import Gauge
from yearn.apy.staking_rewards import get_staking_rewards_apr
from yearn.debug import Debug
from yearn.prices.curve import curve, curve_contracts
from yearn.utils import contract


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

BOOST = {
    Network.Mainnet: MAX_BOOST,
    Network.Fantom: 1.0,
    Network.Arbitrum: 1.0,
    Network.Optimism: 1.0,
}

def get_gauge_relative_weight_for_sidechain(gauge_address):
    url = os.getenv("MAINNET_PROVIDER", None)
    if not url:
        raise ValueError("Erorr! Can't connect to mainnet without a provider URL, please specify $MAINNET_PROVIDER!")

    # some curve gauge metadata like relative_weight is managed by the gauge controller on ethereum mainnet
    gauge_controller = curve_contracts[Network.Mainnet]["gauge_controller"]

    # encode the payload to the ethereum mainnet RPC because we're connected to a sidechain
    function_signature = fourbyte("gauge_relative_weight(address)").hex()
    address_param = encode_single('address', gauge_address).hex()
    data = f"0x{function_signature}{address_param}"

    # hardcode block to "latest" here so it's resolved on the mainnet node,
    # it's a different block than the chain.height this script is running
    # but should be close enough for our calculations
    block = "latest"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": gauge_controller,
                "data": data
            }, block
        ],
        "id": 1
    }
    headers = {'Content-type': 'application/json'}
    res = requests.post(url, data=json.dumps(payload), headers=headers)
    result = res.json()
    return int(result["result"], 16)


async def simple(vault, samples: ApySamples) -> Apy:
    lp_token = vault.token.address
    pool_address = (await y_curve.get_pool(lp_token)).address
    gauge_address = curve.get_gauge(pool_address, lp_token)
    if gauge_address is None:
        raise ApyError("crv", "no gauge")

    block = samples.now
    gauge = await Contract.coroutine(gauge_address)
    if chain.id == Network.Mainnet:
        try:
            controller = await gauge.controller.coroutine()
            controller = await Contract.coroutine(controller)
        except:
            # newer gauges do not have a 'controller' method
            controller = curve.gauge_controller

        gauge_weight = controller.gauge_relative_weight.call(gauge_address, block_identifier=block)
        gauge_inflation_rate = await gauge.inflation_rate.coroutine(block_identifier=block)
    else:
        gauge_weight = get_gauge_relative_weight_for_sidechain(gauge_address)  # TODO: make this non-blocking
        epoch = int(time() / SECONDS_PER_WEEK)
        gauge_inflation_rate = await gauge.inflation_rate.coroutine(epoch, block_identifier=block)

    gauge_working_supply = await gauge.working_supply.coroutine(block_identifier=block)
    if gauge_working_supply == 0:
        raise ApyError("crv", "gauge working supply is zero")

    pool = await Contract.coroutine(pool_address)

    return await calculate_simple(
        vault,
        Gauge(lp_token, pool, gauge, gauge_weight, gauge_inflation_rate, gauge_working_supply),
        samples
    )

async def calculate_simple(vault, gauge: Gauge, samples: ApySamples) -> Apy:
    block = samples.now

    base_asset_price = await magic.get_price(gauge.lp_token, block=block, sync=False)
    if not base_asset_price:
        raise ValueError(f"Error! Could not find price for {gauge.lp_token} at block {block}")

    crv_price = await asyncio.gather(
        magic.get_price(curve.crv, block=block, sync=False)
    )

    if chain.id == Network.Mainnet:
        yearn_voter = addresses[chain.id]['yearn_voter_proxy']
        y_working_balance, y_gauge_balance = await asyncio.gather(
            gauge.gauge.working_balances.coroutine(yearn_voter, block_identifier=block),
            gauge.gauge.balanceOf.coroutine(yearn_voter, block_identifier=block),
        )
    else:
        y_working_balance = 0
        y_gauge_balance = 0
        reward_token = await gauge.gauge.reward_tokens.coroutine(0)
        reward_data = await gauge.gauge.reward_data.coroutine(reward_token)

    base_apr = gauge.calculate_base_apr(BOOST[chain.id], float(crv_price), base_asset_price)
    if base_apr > 1000:
        raise ApyError('crv', f'base apr too high: {base_apr}', f'MAX BOOST: {MAX_BOOST}  crv price: {crv_price}  base asset price: {base_asset_price}')
    
    voter_proxy = addresses[chain.id]['yearn_voter_proxy'] if chain.id in addresses else None
    y_boost = await gauge.calculate_boost(BOOST[chain.id], voter_proxy, block)

    # FIXME: The HBTC v1 vault is currently still earning yield, but it is no longer boosted.
    if vault and vault.vault.address == "0x46AFc2dfBd1ea0c0760CAD8262A5838e803A37e5":
        y_boost = 1
        crv_debt_ratio = 1
    
    # The stETH vault is currently earning LDO, everyone gets max boost.
    if vault and vault.vault.address == "0x5B8C556B8b2a78696F0B9B830B3d67623122E270":
        y_boost = MAX_BOOST
        crv_debt_ratio = 1

    # TODO: come up with cleaner way to deal with these new gauge rewards
    reward_apr = 0
    if hasattr(gauge.gauge, "reward_contract"):
        reward_address = await gauge.gauge.reward_contract.coroutine()
        if reward_address != ZERO_ADDRESS:
            reward_apr = await rewards(reward_address, pool_price, base_asset_price, block=block)
    elif hasattr(gauge.gauge, "reward_data"): # this is how new gauges, starting with MIM, show rewards
        # get our token
        # TODO: consider adding for loop with [gauge.reward_tokens(i) for i in range(gauge.reward_count())] for multiple rewards tokens
        gauge_reward_token = await gauge.gauge.reward_tokens.coroutine(0)
        if gauge_reward_token in [ZERO_ADDRESS]:
            logger.warn(f"no reward token for gauge {str(gauge.gauge)}")
        else:
            reward_data, token_price, total_supply = await asyncio.gather(
                gauge.gauge.reward_data.coroutine(gauge_reward_token),
                _get_reward_token_price(gauge_reward_token),
                gauge.gauge.totalSupply.coroutine(),
            )
            rate = reward_data['rate']
            period_finish = reward_data['period_finish']
            current_time = time() if block is None else await get_block_timestamp_async(block)
            if period_finish < current_time:
                reward_apr = 0
            else:
                reward_apr = (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / ((pool_price / 1e18) * (total_supply / 1e18) * base_asset_price)
    else:
        reward_apr = 0

    get_virtual_price = gauge.pool.get_virtual_price.coroutine
    now_price = await get_virtual_price(block_identifier=samples.now)
    try:
        week_ago_price = await get_virtual_price(block_identifier=samples.week_ago)
    except ValueError:
        raise ApyError("crv", "insufficient data")

    now_point = SharePricePoint(samples.now, now_price)
    week_ago_point = SharePricePoint(samples.week_ago, week_ago_price)

    # FIXME: crvANKR's pool apy going crazy
    if vault and vault.vault.address == "0xE625F5923303f1CE7A43ACFEFd11fd12f30DbcA4":
        pool_apy = 0

    # Curve USDT Pool yVault apr is way too high which fails the apy calculations with a OverflowError
    elif vault and vault.vault.address == "0x28a5b95C101df3Ded0C0d9074DB80C438774B6a9":
        pool_apy = 0

    else:
        try:
            pool_apr = calculate_roi(now_point, week_ago_point)
            pool_apy = (((pool_apr / 365) + 1) ** 365) - 1
        except OverflowError:
            raise ApyError("crv", "overflow error on pool_apy")

    # prevent circular import for partners calculations
    from yearn.v2.vaults import Vault as VaultV2

    if vault:
        if isinstance(vault, VaultV2):
            vault_contract = vault.vault
            if len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, "keepCRV"):
                crv_keep_crv = await vault.strategies[0].strategy.keepCRV.coroutine(block_identifier=block) / 1e4
            elif len(vault.strategies) > 0 and hasattr(vault.strategies[0].strategy, "keepCrvPercent"):
                crv_keep_crv = await vault.strategies[0].strategy.keepCrvPercent.coroutine(block_identifier=block) / 1e4
            else:
                crv_keep_crv = 0
            performance = await vault_contract.performanceFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault_contract, "performanceFee") else 0
            management = await vault_contract.managementFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault_contract, "managementFee") else 0
        else:
            strategy = vault.strategy
            strategist_performance = await strategy.performanceFee.coroutine(block_identifier=block) if hasattr(strategy, "performanceFee") else 0
            strategist_reward = await strategy.strategistReward.coroutine(block_identifier=block) if hasattr(strategy, "strategistReward") else 0
            treasury = await strategy.treasuryFee.coroutine(block_identifier=block) if hasattr(strategy, "treasuryFee") else 0
            crv_keep_crv = await strategy.keepCRV.coroutine(block_identifier=block) / 1e4 if hasattr(strategy, "keepCRV") else 0

            performance = (strategist_reward + strategist_performance + treasury) / 1e4
            management = 0
    else:
        # used for APY calculation previews
        performance = 0.1
        management = 0
        crv_keep_crv = 0
    
    cvx_vault = None
    # if the vault consists of only a convex strategy then return 
    # specialized apy calculations for convex
    if _ConvexVault.is_convex_vault(vault):
        cvx_strategy = vault.strategies[0].strategy
        cvx_vault = _ConvexVault(cvx_strategy, vault, gauge.gauge)
        return await cvx_vault.apy(base_asset_price, pool_price, base_apr, pool_apy, management, performance)

    # if the vault has two strategies then the first is curve and the second is convex
    if isinstance(vault, VaultV2) and len(vault.strategies) == 2: # this vault has curve and convex

        # The first strategy should be curve, the second should be convex.
        # However the order on the vault object here does not correspond
        # to the order on the withdrawal queue on chain, therefore we need to 
        # re-order so convex is always second if necessary 
        first_strategy = vault.strategies[0].strategy
        second_strategy = vault.strategies[1].strategy

        crv_strategy = first_strategy
        cvx_strategy = second_strategy
        if not _ConvexVault.is_convex_strategy(vault.strategies[1]):
            cvx_strategy = first_strategy
            crv_strategy = second_strategy

        if _ConvexVault.is_convex_strategy(cvx_strategy):
            cvx_vault = _ConvexVault(cvx_strategy, vault, gauge.gauge)
            strategies_data, cvx_apy_data = await asyncio.gather(
                vault.vault.strategies.coroutine(crv_strategy),
                cvx_vault.get_detailed_apy_data(base_asset_price, pool_price, base_apr)
            )
            crv_debt_ratio = strategies_data[2] / 1e4
        else:
            # TODO handle this case
            logger.warn(f"no APY calculations for strategy {str(cvx_strategy)}")
            cvx_apy_data = ConvexDetailedApyData()
            crv_debt_ratio = 1
    else:
        cvx_apy_data = ConvexDetailedApyData()
        crv_debt_ratio = 1

    crv_apr = base_apr * y_boost + reward_apr
    if crv_apr > 1000:
        raise ApyError('crv', f'crv apr too high: {crv_apr}', f'base apr: {base_apr}  yboost: {y_boost}  reward apr: {reward_apr}')
    
    crv_apr_minus_keep_crv = base_apr * y_boost * (1 - crv_keep_crv)

    gross_apr = (1 + (crv_apr * crv_debt_ratio + cvx_apy_data.cvx_apr * cvx_apy_data.cvx_debt_ratio)) * (1 + pool_apy) - 1
    if gross_apr > 1000:
        raise ApyError('crv', f'gross apr too high: {gross_apr}', f'crv apr: {crv_apr}  crv debt ratio: {crv_debt_ratio}  cvx apr: {cvx_apy_data.cvx_apr}  cvx debt ratio: {cvx_apy_data.cvx_debt_ratio}  pool apy: {pool_apy}')

    cvx_net_apr = (cvx_apy_data.cvx_apr_minus_keep_crv + cvx_apy_data.convex_reward_apr) * (1 - performance) - management
    cvx_net_farmed_apy = (1 + (cvx_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    cvx_net_apy = ((1 + cvx_net_farmed_apy) * (1 + pool_apy)) - 1

    crv_net_apr = (crv_apr_minus_keep_crv + reward_apr) * (1 - performance) - management
    crv_net_farmed_apy = float(Decimal(1 + (crv_net_apr / COMPOUNDING)) ** COMPOUNDING - 1)
    crv_net_apy = ((1 + crv_net_farmed_apy) * (1 + pool_apy)) - 1

    net_apy = crv_net_apy * crv_debt_ratio + cvx_net_apy * cvx_apy_data.cvx_debt_ratio
  
    boost = y_boost * crv_debt_ratio
    if cvx_vault:
        # add more boost to the existing yearn boost based on the convex data
        cvx_boost = await cvx_vault._get_cvx_boost()
        boost += cvx_boost * cvx_apy_data.cvx_debt_ratio

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

    staking_rewards_apr = await get_staking_rewards_apr(vault, samples)
    if os.getenv("DEBUG", None):
        logger.info(pformat(Debug().collect_variables(locals())))
    return Apy("crv", gross_apr, net_apy, fees, composite=composite, staking_rewards_apr=staking_rewards_apr)

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

        return len(vault.strategies) == 1 and _ConvexVault.is_convex_strategy(vault.strategies[0])

    @staticmethod
    def is_convex_strategy(strategy) -> bool:
        if isinstance(strategy.name, str):
            return "convex" in strategy.name.lower()
        else:
            return "convex" in strategy.name().lower()

    async def apy(self, base_asset_price, pool_price, base_apr, pool_apy: float, management_fee: float, performance_fee: float) -> Apy:
        """The standard APY data."""
        apy_data = await self.get_detailed_apy_data(base_asset_price, pool_price, base_apr)
        gross_apr = (1 + (apy_data.cvx_apr * apy_data.cvx_debt_ratio)) * (1 + pool_apy) - 1

        cvx_net_apr = (apy_data.cvx_apr_minus_keep_crv + apy_data.convex_reward_apr) * (1 - performance_fee) - management_fee
        cvx_net_farmed_apy = (1 + (cvx_net_apr / COMPOUNDING)) ** COMPOUNDING - 1
        cvx_net_apy = ((1 + cvx_net_farmed_apy) * (1 + pool_apy)) - 1

        if os.getenv("DEBUG", None):
            logger.info(pformat(Debug().collect_variables(locals())))

        # 0.3.5+ should never be < 0% because of management
        if cvx_net_apy < 0 and Version(self.vault.api_version) >= Version("0.3.5"): 
            cvx_net_apy = 0

        fees = ApyFees(performance=performance_fee, management=management_fee, cvx_keep_crv=apy_data.cvx_keep_crv)
        return Apy("convex", gross_apr, cvx_net_apy, fees)

    async def get_detailed_apy_data(self, base_asset_price, pool_price, base_apr) -> ConvexDetailedApyData:
        """Detailed data about the apy."""
        # some strategies have a localCRV property which is used based on a flag, otherwise
        # falling back to the global curve config contract.
        # note the spelling mistake in the variable name uselLocalCRV
        if os.getenv("DEBUG", None):
            logger.info(pformat(Debug().collect_variables(locals())))

        if hasattr(self._cvx_strategy, "uselLocalCRV"):
            use_local_crv = self._cvx_strategy.uselLocalCRV(block_identifier=self.block)
            if use_local_crv:
                cvx_keep_crv = self._cvx_strategy.localCRV(block_identifier=self.block)  / 1e4
            else:
                curve_global = contract(self._cvx_strategy.curveGlobal(block_identifier=self.block))
                cvx_keep_crv = curve_global.keepCRV(block_identifier=self.block) / 1e4
        elif hasattr(self._cvx_strategy, "keepCRV"):
            cvx_keep_crv = self._cvx_strategy.keepCRV(block_identifier=self.block) / 1e4
        else:
            # the experimental vault 0xe92AE2cF5b373c1713eB5855D4D3aF81D8a8aCAE yvCurvexFraxTplLP-U
            # has a strategy 0x06aee67AC42473E9F0e7DC1A6687A1F26C8136A3 ConvexTempleDAO-U which doesn't have
            # uselLocalCRV nor keepCRV
            cvx_keep_crv = 0

        cvx_booster = await Contract.coroutine(addresses[chain.id]['convex_booster'])
        cvx_fee, convex_reward_apr, cvx_boost, cvx_printed_as_crv = await asyncio.gather(
            self._get_convex_fee(cvx_booster, self.block),
            self._get_reward_apr(self._cvx_strategy, cvx_booster, base_asset_price, pool_price, self.block),
            self._get_cvx_boost(),
            self._get_cvx_emissions_converted_to_crv(),
        )

        cvx_apr = ((1 - cvx_fee) * cvx_boost * base_apr) * (1 + cvx_printed_as_crv) + convex_reward_apr
        cvx_apr_minus_keep_crv = ((1 - cvx_fee) * cvx_boost * base_apr) * ((1 - cvx_keep_crv) + cvx_printed_as_crv)

        if os.getenv("DEBUG", None):
            logger.info(pformat(Debug().collect_variables(locals())))

        return ConvexDetailedApyData(cvx_apr, cvx_apr_minus_keep_crv, cvx_keep_crv, self._debt_ratio, convex_reward_apr)

    async def _get_cvx_emissions_converted_to_crv(self) -> float:
        """The amount of CVX emissions at the current block for a given pool, converted to CRV (from a pricing standpoint) to ease calculation of total APY."""
        crv_price, cvx = await asyncio.gather(
            magic.get_price(curve.crv, block=self.block, sync=False),
            Contract.coroutine(addresses[chain.id]['cvx']),
        )
        total_cliff = 1e3 # the total number of cliffs to happen
        max_supply = 1e2 * 1e6 * 1e18 # the maximum amount of CVX that will be minted
        reduction_per_cliff = 1e23 # the reduction in emission per cliff
        supply = await cvx.totalSupply.coroutine(block_identifier=self.block) # current supply of CVX 
        cliff = supply / reduction_per_cliff # the current cliff we're on
        if supply <= max_supply:
            reduction = total_cliff - cliff
            cvx_minted = reduction / total_cliff
            cvx_price = await magic.get_price(cvx, block=self.block, sync=False)
            converted_cvx = cvx_price / crv_price
            return cvx_minted * converted_cvx
        else:
            return 0

    async def _get_cvx_boost(self) -> float:
        """The Curve boost (1-2.5x) being applied to this pool thanks to veCRV locked in Convex's voter proxy."""
        convex_voter = addresses[chain.id]['convex_voter_proxy']
        cvx_working_balance, cvx_gauge_balance = await asyncio.gather(
            self.gauge.working_balances.coroutine(convex_voter, block_identifier=self.block),
            self.gauge.balanceOf.coroutine(convex_voter, block_identifier=self.block), 
        )

        if cvx_gauge_balance > 0:
            return cvx_working_balance / (PER_MAX_BOOST * cvx_gauge_balance) or 1
        else:
            return BOOST[chain.id]

    async def _get_reward_apr(self, cvx_strategy, cvx_booster, base_asset_price, pool_price, block=None) -> float:
        """The cumulative apr of all extra tokens that are emitted by depositing 
        to Convex, assuming that they will be sold for profit.
        """
        # Convex hBTC strategy uses id rather than pid - 0x7Ed0d52C5944C7BF92feDC87FEC49D474ee133ce
        pid = await (cvx_strategy.id.coroutine() if hasattr(cvx_strategy, "id") else cvx_strategy.pid.coroutine())
        # pull data from convex's virtual rewards contracts to get bonus rewards
        pool_info = await cvx_booster.poolInfo.coroutine(pid)
        rewards_contract = await Contract.coroutine(pool_info["crvRewards"])
            
        rewards_length = await rewards_contract.extraRewardsLength.coroutine()
        current_time = time() if block is None else await get_block_timestamp_async(block)
        if rewards_length == 0:
            return 0

        convex_reward_apr = 0 # reset our rewards apr if we're calculating it via convex

        for x in range(rewards_length):
            virtual_rewards_pool = await Contract.coroutine(await rewards_contract.extraRewards.coroutine(x))
                # do this for all assets, which will duplicate much of the curve info but we don't want to miss anything
            if await virtual_rewards_pool.periodFinish.coroutine() > current_time:
                reward_token = await virtual_rewards_pool.rewardToken.coroutine()
                reward_token_price, reward_rate, total_supply = await asyncio.gather(
                    _get_reward_token_price(reward_token, block),
                    virtual_rewards_pool.rewardRate.coroutine(),
                    virtual_rewards_pool.totalSupply.coroutine(),
                )

                reward_apr = (reward_rate * SECONDS_PER_YEAR * reward_token_price) / (base_asset_price * (pool_price / 1e18) * total_supply)
                convex_reward_apr += reward_apr

        return convex_reward_apr

    async def _get_convex_fee(self, cvx_booster, block=None) -> float:
        """The fee % that Convex charges on all CRV yield."""
        cvx_lock_incentive, cvx_staker_incentive, cvx_earmark_incentive, cvx_platform_fee = await asyncio.gather(
            cvx_booster.lockIncentive.coroutine(block_identifier=block),
            cvx_booster.stakerIncentive.coroutine(block_identifier=block),
            cvx_booster.earmarkIncentive.coroutine(block_identifier=block),
            cvx_booster.platformFee.coroutine(block_identifier=block),
        )
        return (cvx_lock_incentive + cvx_staker_incentive + cvx_earmark_incentive + cvx_platform_fee) / 1e4

    @property
    def _debt_ratio(self) -> float:
        """The debt ratio of the Convex strategy."""
        return self.vault.vault.strategies(self._cvx_strategy)[2] / 1e4


@lru_cache
def _get_rkp3r() -> Contract:
    return patch_contract(interface.rKP3R(addresses[chain.id]['rkp3r_rewards']), dank_w3)

async def _get_reward_token_price(reward_token, block=None):
    if chain.id not in addresses:
        return await magic.get_price(reward_token, block=block, sync=False)

    # if the reward token is rKP3R we need to calculate it's price in 
    # terms of KP3R after the discount
    contract_addresses = addresses[chain.id]
    if reward_token == contract_addresses['rkp3r_rewards']:
        price, discount = await asyncio.gather(
            magic.get_price(contract_addresses['kp3r'], block=block, sync=False),
            _get_rkp3r().discount.coroutine(block_identifier=block),
        )
        return price * (100 - discount) / 100
    else:
        return await magic.get_price(reward_token, block=block, sync=False)
