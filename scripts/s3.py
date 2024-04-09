import asyncio
import dataclasses
import itertools
import json
import logging
import os
import shutil
import traceback
import warnings
from datetime import datetime
from decimal import Decimal
from time import time
from typing import Union

import boto3
import requests
import sentry_sdk
from brownie import chain
from brownie.exceptions import BrownieEnvironmentWarning
from telegram.error import BadRequest
from y import ERC20, Contract, Network
from y.contracts import contract_creation_block_async
from y.exceptions import yPriceMagicError

from yearn import logs
from yearn.apy import (Apy, ApyBlocks, ApyFees, ApyPoints, ApySamples,
                       get_samples)
from yearn.common import Tvl
from yearn.exceptions import EmptyS3Export
from yearn.graphite import send_metric
from yearn.special import Backscratcher, YveCRVJar
from yearn.utils import chunks, contract
from yearn.v1.registry import Registry as RegistryV1
from yearn.v1.vaults import VaultV1
from yearn.v2.registry import Registry as RegistryV2
from yearn.v2.vaults import Vault as VaultV2

sentry_sdk.set_tag('script','s3')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

METRIC_NAME = "yearn.exporter.apy"

logs.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


async def wrap_vault(
    vault: Union[VaultV1, VaultV2], samples: ApySamples, aliases: dict, icon_url: str, assets_metadata: dict
) -> dict:
    
    # We don't need results for these right away but they take a while so lets start them now
    inception_fut = asyncio.create_task(contract_creation_block_async(str(vault.vault)))
    apy_fut = asyncio.create_task(get_apy(vault, samples))
    tvl_fut = asyncio.create_task(vault.tvl())

    if isinstance(vault, VaultV1):
        strategies = [
            {
                "address": str(vault.strategy),
                "name": await vault.strategy.getName.coroutine() if hasattr(vault.strategy, "getName") else vault.strategy._name,
            }
        ]
    else:
        strategies = [{"address": str(strategy.strategy), "name": strategy.name} for strategy in vault.strategies]

    token_alias = aliases[str(vault.token)]["symbol"] if str(vault.token) in aliases else await ERC20(vault.token, asynchronous=True).symbol
    vault_alias = token_alias

    migration = None

    if str(vault.vault) in assets_metadata:
        migration = {"available": assets_metadata[str(vault.vault)][1], "address": assets_metadata[str(vault.vault)][2]}
    
    object = {
        "inception": await inception_fut,
        "address": str(vault.vault),
        "symbol": vault.symbol if hasattr(vault, "symbol") else await ERC20(vault.vault, asynchronous=True).symbol,
        "name": vault.name,
        "display_name": vault_alias,
        "icon": icon_url % str(vault.vault),
        "token": {
            "name": await ERC20(vault.token, asynchronous=True).name if hasattr(vault.token, "name") else vault.token._name,
            "symbol": await ERC20(vault.token, asynchronous=True).symbol if hasattr(vault.token, "symbol") else None,
            "address": str(vault.token),
            "decimals": await ERC20(vault.token, asynchronous=True).decimals if hasattr(vault.token, "decimals") else None,
            "display_name": token_alias,
            "icon": icon_url % str(vault.token),
        },
        "tvl": dataclasses.asdict(await tvl_fut),
        "apy": dataclasses.asdict(await apy_fut),
        "strategies": strategies,
        "endorsed": vault.is_endorsed if hasattr(vault, "is_endorsed") else True,
        "version": vault.api_version if hasattr(vault, "api_version") else "0.1",
        "decimals": vault.decimals if hasattr(vault, "decimals") else await ERC20(vault.vault, asynchronous=True).decimals,
        "type": "v2" if isinstance(vault, VaultV2) else "v1",
        "emergency_shutdown": await vault.vault.emergencyShutdown.coroutine() if hasattr(vault.vault, "emergencyShutdown") else False,
        "updated": int(time()),
        "migration": migration,
    }

    if chain.id == 1 and any([isinstance(vault, t) for t in [Backscratcher, YveCRVJar]]):
        object["special"] = True

    return object


async def get_apy(vault, samples) -> Apy:
    try:
        return await vault.apy(samples)
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
    
        
async def get_assets_metadata(vault_v2: list) -> dict:
    vault_addresses = [str(vault.vault) for vault in vault_v2]
    assets_dynamic_data = []
    # if we have an address provider and factory_registry_adapter, we can split the vaults
    factory_address_provider, factory_registry_adapter = await asyncio.gather(
        get_factory_address_provider(), get_factory_registry_adapter(),
    )
    if factory_address_provider and factory_registry_adapter:
        # factory vaults
        factories = await asyncio.gather(*[Contract.coroutine(c) for c in await factory_address_provider.assetsAddresses.coroutine()])
        factory_addresses = [str(factory) for factory in factories]
        assets_dynamic_data += await get_assets_dynamic(factory_registry_adapter, factory_addresses)
        # non-factory vaults
        non_factory_addresses = [va for va in vault_addresses if va not in factory_addresses]
        assets_dynamic_data += await get_assets_dynamic(await get_registry_adapter(), non_factory_addresses)

    # normal case without any address provider
    else:
        assets_dynamic_data += await get_assets_dynamic(await get_registry_adapter(), vault_addresses)

    assets_metadata = {}
    for datum in assets_dynamic_data:
        assets_metadata[datum[0]] = datum[-1]
    return assets_metadata


async def get_assets_dynamic(registry_adapter: Contract, addresses: list) -> list:
    return await asyncio.gather(*[registry_adapter.assetDynamic.coroutine(address) for address in addresses])


async def get_registry_adapter():
    if chain.id == Network.Mainnet:
        # TODO Fix ENS resolution for lens.ychad.eth
        registry_adapter_address = "0x240315db938d44bb124ae619f5Fd0269A02d1271"
    elif chain.id == Network.Fantom:
        registry_adapter_address = "0xF628Fb7436fFC382e2af8E63DD7ccbaa142E3cd1"
    elif chain.id == Network.Arbitrum:
        registry_adapter_address = "0x57AA88A0810dfe3f9b71a9b179Dd8bF5F956C46A"
    elif chain.id == Network.Optimism:
        registry_adapter_address = "0xBcfCA75fF12E2C1bB404c2C216DBF901BE047690"
    elif chain.id == Network.Base:
        registry_adapter_address = "0xACd0CEa837A6E6f5824F4Cac6467a67dfF4B0868"
    return await Contract.coroutine(registry_adapter_address)


async def get_factory_address_provider():
    if chain.id == Network.Mainnet:
        return await Contract.coroutine("0xA654Be30cb4A1E25d18DA0629e48b13fb970d5bE")
    else:
        return None


async def get_factory_registry_adapter():
    if chain.id == Network.Mainnet:
        return await Contract.coroutine("0x984550cE9e58A8f76184e1b41Dd08Fbf7B6d2762")
    else:
        return None


def main():
    asyncio.get_event_loop().run_until_complete(_main())


def _get_export_mode():
    allowed_export_modes = ["endorsed", "experimental"]
    export_mode = os.getenv("EXPORT_MODE", "endorsed")
    if export_mode not in allowed_export_modes:
        raise ValueError(f"export_mode must be one of {allowed_export_modes}")
    return export_mode
  
async def _main():
    export_mode = _get_export_mode()
    metric_tags = {"chain": chain.id, "export_mode": export_mode}
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

    registry_v2 = RegistryV2(include_experimental=(export_mode == "experimental"))

    if chain.id == Network.Mainnet:
        special = [YveCRVJar(), Backscratcher()]
        registry_v1 = RegistryV1()
        vaults = list(itertools.chain(special, registry_v1.vaults, registry_v2.vaults, registry_v2.experiments))
    else:
        vaults = registry_v2.vaults

    if len(vaults) == 0:
        raise ValueError(f"No vaults found for chain_id: {chain.id}")

    assets_metadata = await get_assets_metadata(registry_v2.vaults)

    data = []
    total = len(vaults)

    for i, vault in enumerate(vaults):
        pos = i + 1
        logger.info(f"wrapping vault [{pos}/{total}]: {vault.name} {str(vault.vault)}")
        data.append(await wrap_vault(vault, samples, aliases, icon_url, assets_metadata))
        logger.info(f"done wrapping vault [{pos}/{total}]: {vault.name} {str(vault.vault)}")

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
    aws_buckets = os.environ.get("AWS_BUCKET", "").split(";")
    aws_endpoint_urls = os.environ.get("AWS_ENDPOINT_URL", "").split(";")
    aws_keys = os.environ.get("AWS_ACCESS_KEY", "").split(";")
    aws_secrets = os.environ.get("AWS_ACCESS_SECRET", "").split(";")

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

    export_mode = _get_export_mode()
    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
    message = f"`[{now}]`\n⚙️ {export_mode} Vaults API for {Network.name()} is updating..."
    ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        message = f"`[{now}]`\n🔥 {export_mode} Vaults API update for {Network.name()} failed!\n"
        with suppress(BadRequest):
            detail_message = (message + f"```\n{tb}\n```")[:4000]
            updater.bot.send_message(chat_id=private_group, text=detail_message, parse_mode="Markdown", reply_to_message_id=ping)
            updater.bot.send_message(chat_id=public_group, text=detail_message, parse_mode="Markdown")
        raise error
    message = f"✅ {export_mode} Vaults API update for {Network.name()} successful!"
    updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)

def _dedecimal(dct: dict):
    """Decimal type cant be json encoded, we make them into floats"""
    for k, v in dct.items():
        if isinstance(v, dict):
            _dedecimal(v)
        elif isinstance(v, Decimal):
            dct[k] = float(v)