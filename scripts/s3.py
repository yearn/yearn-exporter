import dataclasses
import traceback
import itertools
import warnings
import logging
import shutil
import json
import os

from datetime import datetime
from typing import Any, Union

from time import time

from brownie.network.contract import Contract
from brownie import web3

from yearn.special import Backscratcher, YveCRVJar

import requests
import boto3

from brownie.exceptions import BrownieEnvironmentWarning
from yearn.apy import ApyFees, ApyPoints, Apy, get_samples, ApySamples, ApyError
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault as VaultV2

from yearn.utils import contract_creation_block

from yearn.prices.magic import PriceError

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def wrap_vault(
    vault: Union[VaultV1, VaultV2], samples: ApySamples, aliases: dict, icon_url: str, assets_metadata: dict
) -> dict:
    apy_error = Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
    try:
        apy = vault.apy(samples)
    except ValueError as error:
        logger.error(error)
        apy = apy_error
    except PriceError as error:
        logger.error(error)
        apy = apy_error

    if isinstance(vault, VaultV1):
        strategies = [
            {
                "address": str(vault.strategy),
                "name": vault.strategy.getName() if hasattr(vault.strategy, "getName") else vault.strategy._name,
            }
        ]
    else:
        strategies = [{"address": str(strategy.strategy), "name": strategy.name} for strategy in vault.strategies]

    inception = contract_creation_block(str(vault.vault))

    token_alias = aliases[str(vault.token)]["symbol"] if str(vault.token) in aliases else vault.token.symbol()
    vault_alias = token_alias

    tvl = vault.tvl()

    migration = None

    if str(vault.vault) in assets_metadata:
        migration = {"available": assets_metadata[str(vault.vault)][1], "address": assets_metadata[str(vault.vault)][2]}

    object = {
        "inception": inception,
        "address": str(vault.vault),
        "symbol": vault.symbol if hasattr(vault, "symbol") else vault.vault.symbol(),
        "name": vault.name,
        "display_name": vault_alias,
        "icon": icon_url % str(vault.vault),
        "token": {
            "name": vault.token.name() if hasattr(vault.token, "name") else vault.token._name,
            "symbol": vault.token.symbol() if hasattr(vault.token, "symbol") else None,
            "address": str(vault.token),
            "decimals": vault.token.decimals() if hasattr(vault.token, "decimals") else None,
            "display_name": token_alias,
            "icon": icon_url % str(vault.token),
        },
        "tvl": dataclasses.asdict(tvl),
        "apy": dataclasses.asdict(apy),
        "strategies": strategies,
        "endorsed": vault.is_endorsed if hasattr(vault, "is_endorsed") else True,
        "version": vault.api_version if hasattr(vault, "api_version") else "0.1",
        "decimals": vault.decimals if hasattr(vault, "decimals") else vault.vault.decimals(),
        "type": "v2" if isinstance(vault, VaultV2) else "v1",
        "emergency_shutdown": vault.vault.emergencyShutdown() if hasattr(vault.vault, "emergencyShutdown") else False,
        "updated": int(time()),
        "migration": migration,
    }

    if any([isinstance(vault, t) for t in [Backscratcher, YveCRVJar]]):
        object["special"] = True

    return object


def get_assets_metadata(vault_v2: list) -> dict:
    registry_v2_adapter = Contract(web3.ens.resolve("lens.ychad.eth"))
    addresses = [str(vault.vault) for vault in vault_v2]
    assets_dynamic_data = registry_v2_adapter.assetsDynamic(addresses)
    assets_metadata = {}
    for datum in assets_dynamic_data:
        assets_metadata[datum[0]] = datum[-1]
    return assets_metadata


def main():
    data = []

    aliases_repo_url = "https://api.github.com/repos/yearn/yearn-assets/git/refs/heads/master"
    aliases_repo = requests.get(aliases_repo_url).json()
    commit = aliases_repo["object"]["sha"]

    icon_url = f"https://rawcdn.githack.com/yearn/yearn-assets/{commit}/icons/tokens/%s/logo-128.png"

    aliases_url = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/aliases.json"
    aliases = requests.get(aliases_url).json()
    aliases = {alias["address"]: alias for alias in aliases}

    samples = get_samples()

    special = [YveCRVJar(), Backscratcher()]
    registry_v1 = RegistryV1()
    registry_v2 = RegistryV2()

    assets_metadata = get_assets_metadata(registry_v2.vaults)

    for vault in itertools.chain(special, registry_v1.vaults, registry_v2.vaults, registry_v2.experiments):
        data.append(wrap_vault(vault, samples, aliases, icon_url, assets_metadata))

    out = "generated"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    vaults_api_path = os.path.join("v1", "chains", "1", "vaults")

    os.makedirs(os.path.join(out, vaults_api_path), exist_ok=True)

    # for vault in data:
    #     with open(os.path.join(namespace_vaults, vault["address"]), "w+") as f:
    #         json.dump(vault, f)

    endorsed = [vault for vault in data if vault["endorsed"]]
    experimental = [vault for vault in data if not vault["endorsed"]]

    vault_api_all = os.path.join(vaults_api_path, "all")
    with open(os.path.join(out, vault_api_all), "w+") as f:
        json.dump(endorsed, f)

    vault_api_experimental = os.path.join(vaults_api_path, "experimental")
    with open(os.path.join(out, vault_api_experimental), "w+") as f:
        json.dump(experimental, f)

    aws_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret = os.environ.get("AWS_ACCESS_SECRET")
    aws_bucket = os.environ.get("AWS_BUCKET")

    s3 = boto3.client("s3", aws_access_key_id=aws_key, aws_secret_access_key=aws_secret)

    print(json.dumps(experimental))
    return

    s3.upload_file(
        os.path.join(out, vault_api_all),
        aws_bucket,
        vault_api_all,
        ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
    )

    s3.upload_file(
        os.path.join(out, vault_api_experimental),
        aws_bucket,
        vault_api_experimental,
        ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
    )


telegram_users_to_alert = ["@nymmrx", "@x48114", "@dudesahn"]


def with_monitoring():
    from telegram.ext import Updater

    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
    message = f"`[{now}]`\n⚙️ API (vaults) is updating..."
    ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        tags = " ".join(telegram_users_to_alert)
        message = f"`[{now}]`\n🔥 API (vaults) update failed!\n```\n{tb}\n```\n{tags}"
        updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
        updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
        raise error
    message = "✅ API (vaults) update successful!"
    updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
