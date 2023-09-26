
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
from msgspec import Struct
from multicall.utils import await_awaitable
from tqdm.asyncio import tqdm_asyncio
from y import ERC20, Contract, Network, magic
from y.exceptions import ContractNotVerified
from y.time import get_block_timestamp_async

from yearn.apy import Apy, ApyFees, get_samples
from yearn.apy.common import SECONDS_PER_YEAR
from yearn.apy.curve.simple import Gauge
from yearn.apy.velo import COMPOUNDING
from yearn.v2.registry import Registry
from yearn.debug import Debug

logger = logging.getLogger(__name__)
sentry_sdk.set_tag('script','curve_apy_previews')

class Drome(Struct):
    """Holds various params for a drome deployment"""
    label: str
    sugar: str
    voter: str
    # A random vault to check fees
    fee_checker: str

try:
    drome = {
        Network.Optimism: Drome(
            label='velo',
            sugar='0x4D996E294B00cE8287C16A2b9A4e637ecA5c939f',
            voter='0x41c914ee0c7e1a5edcd0295623e6dc557b5abf3c',
            fee_checker='0xbC61B71562b01a3a4808D3B9291A3Bf743AB3361',
        ),
        Network.Base: Drome(
            label='aero',
            sugar='0x2073D8035bB2b0F2e85aAF5a8732C6f397F9ff9b',
            voter='0x16613524e02ad97eDfeF371bC883F2F5d6C480A5',
            fee_checker='0xEcFc1e5BDa4d4191c9Cab053ec704347Db87Be5d',
        ),
    }[chain.id]
except KeyError:
    raise ValueError(f"there is no drome on unsupported network: {chain.id}")

fee_checker = Contract(drome.fee_checker)
performance_fee = fee_checker.performanceFee() / 1e4
management_fee = fee_checker.managementFee() / 1e4
fee_checker_strat = Contract(fee_checker.withdrawalQueue(0))

keep = fee_checker_strat.localKeepVELO() / 1e4
unkeep = 1 - keep

fees = ApyFees(performance=performance_fee, management=management_fee, keep_velo=keep)

def main():
    _upload(await_awaitable(_build_data()))

async def _build_data():
    start = int(time())
    block = get_samples().now
    data = [d for d in await tqdm_asyncio.gather(*[_build_data_for_lp(lp, block) for lp in await _get_lps_with_vault_potential()]) if d]
    for d in data:
        d['updated'] = start
    print(data)
    return data

async def _get_lps_with_vault_potential() -> List[dict]:
    sugar_oracle = await Contract.coroutine(drome.sugar)
    current_vaults = Registry(watch_events_forever=False, include_experimental=False).vaults
    current_underlyings = [str(vault.token) for vault in current_vaults]
    return [lp for lp in await sugar_oracle.all.coroutine(999999999999999999999, 0, ZERO_ADDRESS) if lp[0] not in current_underlyings and lp[11] != ZERO_ADDRESS]

async def _build_data_for_lp(lp: dict, block: Optional[int] = None) -> Optional[dict]:
    lp_token = lp[0]
    gauge_name = lp[1]
    
    try:
        gauge = await _load_gauge(lp, block=block)
    except ContractNotVerified as e:
        return {
            "gauge_name": gauge_name,
            "apy": dataclasses.asdict(Apy("error:unverified", 0, 0, fees, error_reason=str(e))),
            "block": block,
        }

    try:
        apy = await _staking_apy(lp, gauge.gauge, block=block) if gauge.gauge_weight > 0 else Apy("zero_weight", 0, 0, fees)
    except Exception as error:
        logger.error(error)
        logger.error(gauge)
        apy = Apy("error", 0, 0, fees, error_reason=":".join(str(arg) for arg in error.args))

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
        "block": block,
    }

async def _load_gauge(lp: dict, block: Optional[int] = None) -> Gauge:
    lp_address = lp[0]
    gauge_address = lp[11]
    voter = await Contract.coroutine(drome.voter)
    pool, gauge, weight = await asyncio.gather(
        Contract.coroutine(lp_address), 
        Contract.coroutine(gauge_address),
        voter.weights.coroutine(lp_address, block_identifier=block),
    )
    inflation_rate, working_supply = await asyncio.gather(
        gauge.rewardRate.coroutine(block_identifier=block),
        gauge.totalSupply.coroutine(block_identifier=block),
    )
    return Gauge(lp_address, pool, gauge, weight, inflation_rate, working_supply)
    
async def _staking_apy(lp: dict, staking_rewards: Contract, block: Optional[int]=None) -> float:
    
    current_time = time() if block is None else await get_block_timestamp_async(block)
    
    reward_token, rate, total_supply, end = await asyncio.gather(
        staking_rewards.rewardToken.coroutine(block_identifier=block),
        staking_rewards.rewardRate.coroutine(block_identifier=block),
        staking_rewards.totalSupply.coroutine(block_identifier=block),
        staking_rewards.periodFinish.coroutine(block_identifier=block),
    )
    
    rate *= unkeep
        
    if end < current_time or total_supply == 0 or rate == 0:
        return Apy(f"v2:{drome.label}_unpopular", gross_apr=0, net_apy=0, fees=fees)
    
    pool_price, token_price = await asyncio.gather(
        magic.get_price(lp[0], block=block, sync=False),
        magic.get_price(reward_token, block=block, sync=False),
    )
    
    gross_apr = (SECONDS_PER_YEAR * (rate / 1e18) * token_price) / (pool_price * (total_supply / 1e18))
    
    net_apr = gross_apr * (1 - performance_fee) - management_fee
    net_apy = (1 + (net_apr / COMPOUNDING)) ** COMPOUNDING - 1
    if os.getenv("DEBUG", None):
        logger.info(pformat(Debug().collect_variables(locals())))
    return Apy(f"v2:{drome.label}", gross_apr=gross_apr, net_apy=net_apy, fees=fees)

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