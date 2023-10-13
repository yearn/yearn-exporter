import asyncio
import dataclasses
import json
import logging
import os
import shutil
import traceback
import warnings
from datetime import datetime
from time import time

import boto3
import requests
import sentry_sdk
from brownie import chain
from brownie.exceptions import BrownieEnvironmentWarning
from telegram.error import BadRequest
from y import Network
from y.contracts import contract_creation_block_async
from y.exceptions import yPriceMagicError

from yearn import logs
from yearn.apy import (Apy, ApyBlocks, ApyFees, ApyPoints, ApySamples,
                       get_samples)
from yearn.exceptions import EmptyS3Export
from yearn.yeth import StYETH

sentry_sdk.set_tag('script','yeth')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logs.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def _create_apy_object(label, product, samples, aliases, icon_url) -> dict:
    inception_fut = asyncio.create_task(contract_creation_block_async(product.address))
    apy_fut = asyncio.create_task(get_apy(product, samples))
    tvl_fut = asyncio.create_task(product.tvl())

    alias = aliases[product.address]["symbol"] if product.address in aliases else product.symbol

    object = {
        "inception": await inception_fut,
        "address": product.address,
        "symbol": product.symbol,
        "name": product.name,
        "display_name": alias,
        "icon": icon_url % product.address,
        "tvl": dataclasses.asdict(await tvl_fut),
        "apy": dataclasses.asdict(await apy_fut),
        "decimals": product.decimals,
        "type": label,
        "updated": int(time())
    }
    return object


async def wrap_stYETH(
  stYETH: StYETH, samples: ApySamples, aliases: dict, icon_url: str
) -> dict:

    stYETHobject = await _create_apy_object("st-YETH", stYETH, samples, aliases, icon_url)
    lstObjects = []
    for lst in stYETH.lsts:
        lstObject = await _create_apy_object("yETH LST", lst, samples, aliases, icon_url)
        lstObject["asset_id"] = lst.asset_id
        lstObjects.append(lstObject)

    stYETHobject["lsts"] = lstObjects
    return stYETHobject


async def get_apy(product, samples) -> Apy:
    try:
        return await product.apy(samples)
    except (ValueError, yPriceMagicError) as error:
        logger.error(error)
        return Apy(
            type="error",
            gross_apr=0,
            net_apy=0,
            fees=ApyFees(0, 0),
            points=ApyPoints(0, 0, 0),
            blocks=ApyBlocks(samples.now, 0, 0, 0),
            error_reason=":".join(str(arg) for arg in error.args),
        )

def main():
    asyncio.get_event_loop().run_until_complete(_main())


async def _main():
    aliases_repo_url = "https://api.github.com/repos/yearn/yearn-assets/git/refs/heads/master"
    aliases_repo = requests.get(aliases_repo_url).json()

    if "object" not in aliases_repo:
        raise KeyError(f"key 'object' not found in {aliases_repo}")

    commit = aliases_repo["object"]["sha"]

    icon_url = f"https://rawcdn.githack.com/yearn/yearn-assets/{commit}/icons/multichain-tokens/{chain.id}/%s/logo-128.png"

    aliases_url = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/aliases.json"
    aliases = requests.get(aliases_url).json()
    aliases = {alias["address"]: alias for alias in aliases}

    samples = get_samples()

    to_export = [await wrap_stYETH(StYETH(), samples, aliases, icon_url)]

    if len(to_export) == 0:
        raise EmptyS3Export(f"No data for vaults was found in generated data, aborting upload")

    file_name, s3_path = _get_export_paths()
    _export(to_export, file_name, s3_path)


def _export(data, file_name, s3_path):
    print(json.dumps(data, indent=4))

    with open(file_name, "w+") as f:
        json.dump(data, f)

    if os.getenv("DEBUG", None):
        return

    for item in _get_s3s():
        s3 = item["s3"]
        aws_bucket = item["aws_bucket"]
        s3.upload_file(
            file_name,
            aws_bucket,
            s3_path,
            ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
        )


def _get_s3s():
    s3s = []
    aws_buckets = os.environ.get("AWS_BUCKET").split(";")
    aws_endpoint_urls = os.environ.get("AWS_ENDPOINT_URL").split(";")
    aws_keys = os.environ.get("AWS_ACCESS_KEY").split(";")
    aws_secrets = os.environ.get("AWS_ACCESS_SECRET").split(";")

    for i in range(len(aws_buckets)):
        aws_bucket = aws_buckets[i]
        aws_endpoint_url = aws_endpoint_urls[i]
        aws_key = aws_keys[i]
        aws_secret = aws_secrets[i]
        kwargs = {}
        if aws_endpoint_url is not None:
            kwargs["endpoint_url"] = aws_endpoint_url
        if aws_key is not None:
            kwargs["aws_access_key_id"] = aws_key
        if aws_secret is not None:
            kwargs["aws_secret_access_key"] = aws_secret

        s3s.append(
          {
            "s3": boto3.client("s3", **kwargs),
            "aws_bucket": aws_bucket
          }
        )

    return s3s


def _get_export_paths():
    out = "generated"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    yeth_api_path = os.path.join("v1", "chains", f"{chain.id}", "yeth")
    file_base_path = os.path.join(out, yeth_api_path)
    os.makedirs(file_base_path, exist_ok=True)

    return file_base_path, yeth_api_path


def with_monitoring():
    if os.getenv("DEBUG", None):
        main()
        return
    from telegram.ext import Updater

    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
    message = f"`[{now}]`\n⚙️ YETH API for {Network.name()} is updating..."
    ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        message = f"`[{now}]`\n🔥 YETH API update for {Network.name()} failed!\n"
        try:
            detail_message = (message + f"```\n{tb}\n```")[:4000]
            updater.bot.send_message(chat_id=private_group, text=detail_message, parse_mode="Markdown", reply_to_message_id=ping)
            updater.bot.send_message(chat_id=public_group, text=detail_message, parse_mode="Markdown")
        except BadRequest:
            pass
            #detail_message = message + f"{error.__class__.__name__}({error})"
            #updater.bot.send_message(chat_id=private_group, text=detail_message, parse_mode="Markdown", reply_to_message_id=ping)
            #updater.bot.send_message(chat_id=public_group, text=detail_message, parse_mode="Markdown")
        raise error
    message = f"✅ YETH API update for {Network.name()} successful!"
    updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
