import dataclasses
import itertools
import json
import logging
import os
import shutil
import traceback
import warnings
from datetime import datetime
from time import time
from typing import Union

import boto3
import requests
import sentry_sdk
from brownie import Contract, chain, web3
from brownie.exceptions import BrownieEnvironmentWarning
from y.exceptions import PriceError
from y.networks import Network

from yearn.apy import (Apy, ApyBlocks, ApyFees, ApyPoints, ApySamples,
                       get_samples)
from yearn.common import Tvl
from yearn.exceptions import EmptyS3Export, PriceError
from yearn.graphite import send_metric
from yearn.special import Backscratcher, YveCRVJar
from yearn.utils import chunks, contract, contract_creation_block
from yearn.v1.registry import Registry as RegistryV1
from yearn.v1.vaults import VaultV1
from yearn.v2.registry import Registry as RegistryV2
from yearn.v2.vaults import Vault as VaultV2

sentry_sdk.set_tag('script','s3')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

METRIC_NAME = "yearn.exporter.apy"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def wrap_vault(
    vault: Union[VaultV1, VaultV2], samples: ApySamples, aliases: dict, icon_url: str, assets_metadata: dict
) -> dict:
    apy_error = Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0), ApyBlocks(samples.now, 0, 0, 0))
    tvl = Tvl(tvl=0)
    try:
        apy = vault.apy(samples)
        tvl = vault.tvl()
    except ValueError as error:
        apy_error.error_reason = ":".join(error.args)
        logger.error(error)
        apy = apy_error
    except PriceError as error:
        apy_error.error_reason = ":".join(error.args)
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

    if chain.id == 1 and any([isinstance(vault, t) for t in [Backscratcher, YveCRVJar]]):
        object["special"] = True

    return object


def get_assets_metadata(vault_v2: list) -> dict:
    vault_addresses = [str(vault.vault) for vault in vault_v2]
    assets_dynamic_data = []
    # if we have an address provider and factory_registry_adapter, we can split the vaults
    if factory_address_provider() and factory_registry_adapter():
        # factory vaults
        factory_addresses = [str(contract(c)) for c in factory_address_provider().assetsAddresses()]
        assets_dynamic_data += get_assets_dynamic(factory_registry_adapter(), factory_addresses)
        # non-factory vaults
        non_factory_addresses = [va for va in vault_addresses if va not in factory_addresses]
        assets_dynamic_data += get_assets_dynamic(registry_adapter(), non_factory_addresses)

    # normal case without any address provider
    else:
        assets_dynamic_data += get_assets_dynamic(registry_adapter(), vault_addresses)

    assets_metadata = {}
    for datum in assets_dynamic_data:
        assets_metadata[datum[0]] = datum[-1]
    return assets_metadata


def get_assets_dynamic(registry_adapter: Contract, addresses: list) -> list:
    assets_dynamic_data = []
    addresses_chunks = chunks(addresses, 20)
    for chunk in addresses_chunks:
        assets_dynamic_data += registry_adapter.assetsDynamic(chunk)
    return assets_dynamic_data


def registry_adapter():
    if chain.id == Network.Mainnet:
        registry_adapter_address = "0x240315db938d44bb124ae619f5Fd0269A02d1271"
    elif chain.id == Network.Fantom:
        registry_adapter_address = "0xF628Fb7436fFC382e2af8E63DD7ccbaa142E3cd1"
    elif chain.id == Network.Arbitrum:
        registry_adapter_address = "0x57AA88A0810dfe3f9b71a9b179Dd8bF5F956C46A"
    elif chain.id == Network.Optimism:
        registry_adapter_address = "0xBcfCA75fF12E2C1bB404c2C216DBF901BE047690"
    return contract(registry_adapter_address)


def factory_address_provider():
    if chain.id == Network.Mainnet:
        return contract("0xA654Be30cb4A1E25d18DA0629e48b13fb970d5bE")
    else:
        return None


def factory_registry_adapter():
    if chain.id == Network.Mainnet:
        return contract("0x984550cE9e58A8f76184e1b41Dd08Fbf7B6d2762")
    else:
        return None

def main():
    data = []
    allowed_export_modes = ["endorsed", "experimental"]
    export_mode = os.getenv("EXPORT_MODE", "endorsed")
    if export_mode not in allowed_export_modes:
        raise ValueError(f"export_mode must be one of {allowed_export_modes}")

    metric_tags = {"chain": chain.id, "export_mode": export_mode}
    aliases_repo_url = "https://api.github.com/repos/yearn/yearn-assets/git/refs/heads/master"
    aliases_repo = requests.get(aliases_repo_url).json()
    commit = aliases_repo["object"]["sha"]

    icon_url = f"https://rawcdn.githack.com/yearn/yearn-assets/{commit}/icons/multichain-tokens/{chain.id}/%s/logo-128.png"

    aliases_url = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/aliases.json"
    aliases = requests.get(aliases_url).json()
    aliases = {alias["address"]: alias for alias in aliases}

    samples = get_samples()

    registry_v2 = RegistryV2(include_experimental=(export_mode == "experimental"))

    if chain.id == Network.Mainnet:
        special = [YveCRVJar(), Backscratcher()]
        registry_v1 = RegistryV1()
        vaults = list(itertools.chain(special, registry_v1.vaults, registry_v2.vaults, registry_v2.experiments))
    else:
        vaults = registry_v2.vaults

    if len(vaults) == 0:
        raise ValueError(f"No vaults found for chain_id: {chain.id}")

    assets_metadata = get_assets_metadata(registry_v2.vaults)

    for vault in vaults:
        data.append(wrap_vault(vault, samples, aliases, icon_url, assets_metadata))

    if len(data) == 0:
        raise ValueError(f"Data is empty for chain_id: {chain.id}")

    to_export = []
    suffix = None
    if export_mode == "endorsed":
        to_export = [vault for vault in data if vault["endorsed"]]
        suffix = "all"
    elif export_mode == "experimental":
        to_export = [vault for vault in data if not vault["endorsed"]]
        suffix = "experimental"

    if len(to_export) == 0:
        raise EmptyS3Export(f"No data for vaults was found in generated data, aborting upload")

    file_name, s3_path = _get_export_paths(suffix)
    _export(to_export, file_name, s3_path)

    # Sent a metric so we can track and alert on if this was successfully generated
    utc_now = datetime.utcnow()
    send_metric(f"{METRIC_NAME}.success", 1, utc_now, tags=metric_tags)


def _export(data, file_name, s3_path):
    print(json.dumps(data, indent=4))

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

    vaults_api_path = os.path.join("v1", "chains", f"{chain.id}", "vaults")

    file_base_path = os.path.join(out, vaults_api_path)
    os.makedirs(file_base_path, exist_ok=True)

    file_name = os.path.join(file_base_path, suffix)
    s3_path = os.path.join(vaults_api_path, suffix)
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
    message = f"`[{now}]`\n⚙️ API (vaults) for {Network(chain.id).name} is updating..."
    ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        export_mode = os.getenv("EXPORT_MODE", "endorsed")
        now = datetime.now()
        message = f"`[{now}]`\n🔥 API ({export_mode} vaults) update for {Network(chain.id).name} failed!\n```\n{tb}\n```"[:4000]
        updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
        updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
        raise error
    message = f"✅ API (vaults) update for {Network(chain.id).name} successful!"
    updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
