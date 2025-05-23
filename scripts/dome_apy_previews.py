import dataclasses
import json
import logging
import os
import re
import shutil
import traceback
from datetime import datetime
from time import sleep, time
from typing import List

import boto3
import requests
import sentry_sdk
from brownie import ZERO_ADDRESS
from brownie.exceptions import ContractNotFound
from multicall.utils import await_awaitable
from y import Contract, Network, PriceError
from y.constants import CHAINID
from y.exceptions import ContractNotVerified

from yearn.apy import Apy, ApyFees, ApyPoints, ApySamples, get_samples
from yearn.apy.curve.simple import Gauge, calculate_simple
from yearn.exceptions import EmptyS3Export

logger = logging.getLogger(__name__)
sentry_sdk.set_tag('script','curve_apy_previews')

chains = {
    Network.Optimism: '0xC5be2c918EB04B091962fDF095A217A55CFA42C5',
    Network.Base: '',
}


def main():
    gauges = _get_gauges()
    data = _build_data(gauges)
    _upload(data)

def _build_data(gauges):
    samples = get_samples()
    data = []
    for name, values in gauges.items():
        m = re.match('^([^\(\)]+) \(.*\)', name)
        gauge_name = m[1]
        try:
            gauge = _extract_gauge(values)
        except ContractNotVerified as e:
            data.append({
                "gauge_name": gauge_name,
                "apy": dataclasses.asdict(Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0), error_reason=str(e))),
                "updated": int(time()),
                "block": samples.now,
            })
            continue
        if not gauge:
            continue

        pool_coins = []
        for i in range(4):
            try:
                coin_address = gauge.pool.coins(i)
            except ValueError as e:
                # If the execution reverted, there is no coin with index i.
                if str(e) == "execution reverted":
                    continue
                raise

            # Sometimes the call returns the zero address instead of reverting. This means there is no coin with index i.
            if coin_address == ZERO_ADDRESS:
                continue

            try:
                if coin_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                    name = "ETH"
                else:
                    c = Contract(coin_address)
                    name = c.name()

                pool_coins.append({"name": name, "address": coin_address})
            except (ContractNotFound, ContractNotVerified, ValueError, AttributeError) as e:
                pool_coins.append({"address": coin_address, "error": str(e)})
                logger.error(f"error for coins({i}) for pool {str(gauge.pool)}")
                logger.error(e)

        apy_error = Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
        try:
            if gauge.gauge_weight > 0:
                apy = await_awaitable(calculate_simple(None, gauge, samples))
            else:
                apy = Apy("zero_weight", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
        except Exception as error:
            apy_error.error_reason = ":".join(str(arg) for arg in error.args)
            logger.error(error)
            logger.error(gauge)
            apy = apy_error

        object = {
            "gauge_name": gauge_name,
            "gauge_address": str(gauge.gauge),
            "pool_address": str(gauge.pool),
            "pool_coins": pool_coins,
            "lp_token": str(Contract(gauge.lp_token)),
            "weight": str(gauge.gauge_weight),
            "inflation_rate": str(gauge.gauge_inflation_rate),
            "working_supply": str(gauge.gauge_working_supply),
            "apy": dataclasses.asdict(apy),
            "updated": int(time()),
            "block": samples.now,
        }
        data.append(object)
    return data

def _extract_gauge(v):
    if v["side_chain"] or v["is_killed"]:
        return None

    pool_address = v["swap"]
    gauge_address = v["gauge"]
    gauge_data = v["gauge_data"]
    gauge_controller = v["gauge_controller"]

    lp_token = v["swap_token"]
    pool = Contract(pool_address)
    gauge = Contract(gauge_address)
    weight = int(gauge_controller["gauge_relative_weight"])
    inflation_rate = int(gauge_data["inflation_rate"])
    working_supply = int(gauge_data["working_supply"])

    return Gauge(lp_token, pool, gauge, weight, inflation_rate, working_supply)


def _get_gauges() -> List[str]:
    if CHAINID not in chains:
        raise ValueError(f"can't get velo gauges for unsupported network: {CHAINID}")
    gauge_factory = Contract(chains[CHAINID])
    return [pool for pool in pools]


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

    api_path = os.path.join("v1", "chains", f"{CHAINID}", "apy-previews")

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
    message = f"`[{now}]`\n⚙️ Curve Previews API for {Network.name()} is updating..."
    ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        message = f"`[{now}]`\n🔥 Curve Previews API update for {Network.name()} failed!\n```\n{tb}\n```"[:4000]
        updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
        updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
        raise error
    message = f"✅ Curve Previews API update for {Network.name()} successful!"
    updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)