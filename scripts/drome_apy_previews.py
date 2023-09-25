
"""
This script produces a list of velodrome/aerodrome gauges for which vaults can be created
"""

import asyncio
import dataclasses
import json
import logging
import os
import shutil
import traceback
from datetime import datetime
from pprint import pformat
from time import time
from typing import List, Optional

import boto3
import sentry_sdk
from brownie import ZERO_ADDRESS, chain
from multicall.utils import await_awaitable
from tqdm.asyncio import tqdm_asyncio
from y import Contract, Network, magic, ERC20
from y.exceptions import ContractNotVerified
from y.time import get_block_timestamp_async

from yearn.apy import Apy, ApyFees, ApyPoints, ApySamples, get_samples
from yearn.apy.common import SECONDS_PER_YEAR
from yearn.apy.curve.simple import Gauge
from yearn.apy.velo import COMPOUNDING
from yearn.debug import Debug

logger = logging.getLogger(__name__)
sentry_sdk.set_tag('script','curve_apy_previews')

sugars = {
    Network.Optimism: '0x4D996E294B00cE8287C16A2b9A4e637ecA5c939f',
    Network.Base: '0x2073D8035bB2b0F2e85aAF5a8732C6f397F9ff9b',
}

voters = {
    # Velodrome
    Network.Optimism: '0x41c914ee0c7e1a5edcd0295623e6dc557b5abf3c',
    # Aerodrome
    Network.Base: '0x16613524e02ad97eDfeF371bC883F2F5d6C480A5',
}

def main():
    _upload(await_awaitable(_build_data()))

async def _build_data():
    start = int(time())
    samples = get_samples()
    data = [d for d in await tqdm_asyncio.gather(*[_build_data_for_lp(lp, samples) for lp in await _get_lps()]) if d]
    for d in data:
        d['updated'] = start
    print(data)
    return data

async def _get_lps() -> List[dict]:
    if chain.id not in sugars:
        raise ValueError(f"can't get balancer gauges for unsupported network: {chain.id}")
    sugar_oracle = await Contract.coroutine(sugars[chain.id])
    return [lp for lp in await sugar_oracle.all.coroutine(999999999999999999999, 0, ZERO_ADDRESS)]

class NoGaugeFound(Exception):
    pass

async def _build_data_for_lp(lp: dict, samples: ApySamples) -> Optional[dict]:
    lp_token = lp[0]
    gauge_name = lp[1]
    
    try:
        gauge = await _load_gauge(lp)
    except NoGaugeFound:
        return None
    except ContractNotVerified as e:
        return {
            "gauge_name": gauge_name,
            "apy": dataclasses.asdict(Apy("error:unverified", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0), error_reason=str(e))),
            "block": samples.now,
        }

    apy_error = Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
    try:
            
        if gauge.gauge_weight > 0:
            apy = await _staking_apy(lp, gauge.gauge, samples)
        else:
            apy = Apy("zero_weight", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
    except Exception as error:
        apy_error.error_reason = ":".join(str(arg) for arg in error.args)
        logger.error(error)
        logger.error(gauge)
        apy = apy_error

    return {
        "gauge_name": gauge_name,
        "gauge_address": str(gauge.gauge),
        "token0": lp[5],
        "token1": lp[8],
        "lp_token": lp_token,
        "weight": str(gauge.gauge_weight),
        "inflation_rate": str(gauge.gauge_inflation_rate),
        "working_supply": str(gauge.gauge_working_supply),
        "apy": dataclasses.asdict(apy),
        "block": samples.now,
    }

async def _load_gauge(lp: dict) -> Gauge:
    lp_address = lp[0]
    gauge_address = lp[11]
    if gauge_address == ZERO_ADDRESS:
        raise NoGaugeFound(f"lp {lp_address} has no gauge")
    voter = await Contract.coroutine(voters[chain.id])
    pool, gauge, weight = await asyncio.gather(
        Contract.coroutine(lp_address), 
        Contract.coroutine(gauge_address),
        voter.weights.coroutine(lp_address),
    )
    inflation_rate, working_supply = await asyncio.gather(gauge.rewardRate.coroutine(), gauge.totalSupply.coroutine())
    return Gauge(lp_address, pool, gauge, weight, inflation_rate, working_supply)
    
async def _staking_apy(lp: dict, staking_rewards: Contract, samples: ApySamples, block: Optional[int]=None) -> float:
    
    current_time = time() if block is None else await get_block_timestamp_async(block)
    
    reward_token, rate, total_supply, end = await asyncio.gather(
        staking_rewards.rewardToken.coroutine(block_identifier=block),
        staking_rewards.rewardRate.coroutine(block_identifier=block),
        staking_rewards.totalSupply.coroutine(block_identifier=block),
        staking_rewards.periodFinish.coroutine(block_identifier=block),
    )
    
    # NOTE: should perf be 0? 
    #performance = await vault.vault.performanceFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault.vault, "performanceFee") else 0
    performance = 0
    # NOTE: should mgmt be 0?
    #management = await vault.vault.managementFee.coroutine(block_identifier=block) / 1e4 if hasattr(vault.vault, "managementFee") else 0
    management = 0
    # since its a fork we still call it keepVELO
    #keep = await vault.strategies[0].strategy.localKeepVELO.coroutine(block_identifier=block) / 1e4 if hasattr(vault.strategies[0].strategy, "localKeepVELO") else 0
    # NOTE: should keep be 0?
    keep = 0
    rate = rate * (1 - keep)
    fees = ApyFees(performance=performance, management=management, keep_velo=keep)
        
    if end < current_time or total_supply == 0 or rate == 0:
        return Apy("v2:aero_unpopular", gross_apr=0, net_apy=0, fees=fees)
    
    pool_price, token_price = await asyncio.gather(
        magic.get_price(lp[0], block=block, sync=False),
        magic.get_price(reward_token, block=block, sync=False),
    )
    
    gross_apr = (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (pool_price * (total_supply / 1e18))
    
    net_apr = gross_apr * (1 - performance) - management 
    net_apy = (1 + (net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    # NOTE: do we need this?
    #staking_rewards_apr = await _get_staking_rewards_apr(reward_token, pool_price, token_price, rate, total_supply, samples)
    if os.getenv("DEBUG", None):
        logger.info(pformat(Debug().collect_variables(locals())))
    return Apy("v2:aero", gross_apr=gross_apr, net_apy=net_apy, fees=fees) #, staking_rewards_apr=staking_rewards_apr)

async def _get_staking_rewards_apr(reward_token: str, lp_price: float, reward_price: float, reward_rate: int, total_supply_staked: int, samples: ApySamples):
    vault_scale = 10 ** 18
    reward_token_scale = await ERC20(reward_token, asynchronous=True).scale
    per_staking_token_rate = (reward_rate / reward_token_scale) / (total_supply_staked / vault_scale)
    rewards_vault_apy = (await rewards_vault.apy(samples)).net_apy
    emissions_apr = SECONDS_PER_YEAR * per_staking_token_rate * reward_price / lp_price
    return emissions_apr * (1 + rewards_vault_apy)

def _upload(data):
    print(json.dumps(data, sort_keys=True, indent=4))

    file_name, s3_path = _get_export_paths("curve-factory")
    with open(file_name, "w+") as f:
        json.dump(data, f)

    if os.getenv("DEBUG", None):
        return

    aws_bucket = os.environ.get("AWS_BUCKET")

    s3 = _get_s3()
    s3.upload_file(
        file_name,
        aws_bucket,
        s3_path,
        ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
    )


def _get_s3():
    aws_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret = os.environ.get("AWS_ACCESS_SECRET")

    kwargs = {}
    if aws_key is not None:
        kwargs["aws_access_key_id"] = aws_key
    if aws_secret is not None:
        kwargs["aws_secret_access_key"] = aws_secret

    return boto3.client("s3", **kwargs)


def _get_export_paths(suffix):
    out = "generated"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    api_path = os.path.join("v1", "chains", f"{chain.id}", "apy-previews")

    file_base_path = os.path.join(out, api_path)
    os.makedirs(file_base_path, exist_ok=True)

    file_name = os.path.join(file_base_path, suffix)
    s3_path = os.path.join(api_path, suffix)
    return file_name, s3_path

def with_monitoring():
    if os.getenv("DEBUG", None):
        main()
        return
    from telegram.ext import Updater

    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
    if Network.name() == "Optimism":
        message = f"`[{now}]`\n⚙️ Velodrome Previews API for {Network.name()} is updating..."
        ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
        ping = ping.message_id
        try:
            main()
        except Exception as error:
            tb = traceback.format_exc()
            now = datetime.now()
            message = f"`[{now}]`\n🔥 Velodrome Previews API update for {Network.name()} failed!\n```\n{tb}\n```"[:4000]
            updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
            updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
            raise error
        message = f"✅ Velodrome Previews API update for {Network.name()} successful!"
        updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
    elif Network.name() == "Base":
        message = f"`[{now}]`\n⚙️ Aerodrome Previews API for {Network.name()} is updating..."
        ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
        ping = ping.message_id
        try:
            main()
        except Exception as error:
            tb = traceback.format_exc()
            now = datetime.now()
            message = f"`[{now}]`\n🔥 Aerodrome Previews API update for {Network.name()} failed!\n```\n{tb}\n```"[:4000]
            updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
            updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
            raise error
        message = f"✅ Aerodrome Previews API update for {Network.name()} successful!"
        updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
    else: 
        message = f"{Network.name()} network not a valid network for previews script."