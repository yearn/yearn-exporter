import json
import logging
import os
import shutil
import traceback
import warnings
from datetime import datetime

import boto3
import sentry_sdk
from brownie import web3
from brownie.exceptions import BrownieEnvironmentWarning
from dotenv import find_dotenv, load_dotenv
from multicall.utils import await_awaitable
from y import Contract

from yearn import logs
from yearn.apy import ApySamples, get_samples
from yearn.prices import curve
from yearn.special import Backscratcher
from yearn.v2.registry import Registry as RegistryV2
from yearn.v2.vaults import Vault as VaultV2

sentry_sdk.set_tag('script','s3_loanscan')

load_dotenv(find_dotenv())


warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logs.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def get_assets_metadata(vault_v2: list) -> dict:
    # TODO Fix ENS resolution for lens.ychad.eth
    registry_v2_adapter = Contract("0x240315db938d44bb124ae619f5Fd0269A02d1271")
    addresses = [str(vault.vault) for vault in vault_v2]
    assets_dynamic_data = registry_v2_adapter.assetsDynamic(addresses)
    assets_metadata = {}
    for datum in assets_dynamic_data:
        assets_metadata[datum[0]] = datum[-1]
    return assets_metadata


def get_formatted_lend_rates(vault: VaultV2, samples: ApySamples) -> list:
    apy = vault.apy(samples)
    lend_rate_apy = apy.net_apy
    lend_rate_apr = ((apy.net_apy + 1) ** (1 / 365) - 1) * 365
    if apy.type == 'crv':
        return [
            {"apr": lend_rate_apr, "apy": lend_rate_apy, "tokenSymbol": Contract(curve_pool_token_address).symbol()}
            for curve_pool_token_address in curve.get_underlying_coins(vault.token)
        ]
    else:
        return [{"apr": lend_rate_apr, "apy": lend_rate_apy, "tokenSymbol": vault.token.symbol()}]


def write_json(json_dict: dict, path: str):
    try:
        with open(path, "w+") as f:
            json.dump(json_dict, f)
    except Exception as error:
        logger.info(f'failed to write {path}')
        logger.error(error)


def main():
    samples = get_samples()
    registry_v2 = RegistryV2()
    vaults = await_awaitable(registry_v2.vaults)
    assets_metadata = get_assets_metadata(vaults)

    loanscan_vault_symbols = []
    loanscan_vault_json = []

    yveCrvVault = Backscratcher()
    try:
        # Get vault symbol and lend rates BEFORE appending to corresponding lists
        # If there is an exception with either, lists won't de-sync
        # Don't simplify below this comment
        yveCrv_symbol = yveCrvVault.vault.symbol()
        yveCrv_lend_rates = get_formatted_lend_rates(yveCrvVault, samples)
        loanscan_vault_symbols.append(yveCrv_symbol)
        loanscan_vault_json.append({"symbol": yveCrv_symbol, "lendRates": yveCrv_lend_rates})
        # Don't simplify above this comment
    except Exception as yveCrvException:
        logger.info(f'failed to reduce yveCrv lendRate, {str(yveCrvVault.vault)} {yveCrvVault}')
        logger.error(yveCrvException)

    for vault in vaults:
        try:
            vault_not_endorsed = not (hasattr(vault, "is_endorsed") and await_awaitable(vault.is_endorsed))
            if vault_not_endorsed:
                continue

            current_vault_address = str(vault.vault)
            next_vault_address = assets_metadata[current_vault_address][2]
            vault_not_migrated = current_vault_address != next_vault_address
            if vault_not_migrated:
                continue

            # Get vault symbol and lend rates BEFORE appending to corresponding lists
            # If there is an exception with either, lists won't de-sync
            # Don't simplify below this comment
            vault_symbol = vault.vault.symbol()
            vault_lend_rates = get_formatted_lend_rates(vault, samples)
            loanscan_vault_symbols.append(vault_symbol)
            loanscan_vault_json.append({"symbol": vault_symbol, "lendRates": vault_lend_rates})
            # Don't simplify above this comment
        except Exception as error:
            logger.info(f'failed to reduce loanscan lendRate for vault {str(vault.vault)} {vault}')
            logger.error(error)

    out_path = "generated"
    base_path_s3 = os.path.join("v1", "chains", "1", "loanscan")
    loanscan_path = os.path.join(out_path, base_path_s3)
    os.makedirs(out_path, exist_ok=True)
    if os.path.isdir(loanscan_path):
        shutil.rmtree(loanscan_path)
    os.makedirs(loanscan_path, exist_ok=True)

    write_json(loanscan_vault_symbols, os.path.join(loanscan_path, "manifest"))
    write_json(loanscan_vault_json, os.path.join(loanscan_path, "all"))
    for loanscan_vault in loanscan_vault_json:
        write_json({"lendRates": loanscan_vault["lendRates"]}, os.path.join(loanscan_path, loanscan_vault["symbol"]))

    aws_bucket = os.environ.get("AWS_BUCKET")
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("AWS_ACCESS_SECRET"),
    )

    for loanscan_json_filename in os.listdir(loanscan_path):
        try:
            file_path = os.path.join(loanscan_path, loanscan_json_filename)
            file_path_s3 = os.path.join(base_path_s3, loanscan_json_filename)
            s3.upload_file(
                file_path,
                aws_bucket,
                file_path_s3,
                ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
            )
        except Exception as error:
            logger.info(f'failed to upload {file_path} to s3')
            logger.error(error)


telegram_users_to_alert = ["@nymmrx", "@x48114", "@dudesahn"]


def with_monitoring():
    from telegram.ext import Updater

    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
    message = f"`[{now}]`\n⚙️ API (loanscan) is updating..."
    ping = updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        tags = " ".join(telegram_users_to_alert)
        message = f"`[{now}]`\n🔥 API (loanscan) update failed!\n```\n{tb}\n```\n{tags}"
        updater.bot.send_message(chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
        updater.bot.send_message(chat_id=public_group, text=message, parse_mode="Markdown")
        raise error
    message = "✅ API (loanscan) update successful!"
    updater.bot.send_message(chat_id=private_group, text=message, reply_to_message_id=ping)
