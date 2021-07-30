from yearn.special import Backscratcher, YveCRVJar
from yearn.v2.registry import Registry as RegistryV2
from yearn.v1.registry import Registry as RegistryV1
from yearn.prices import curve
from yearn.apy import get_samples
from brownie import web3
from brownie.network.contract import Contract
from brownie.exceptions import BrownieEnvironmentWarning
import boto3
from datetime import datetime
import os
import json
import shutil
import logging
import warnings
import itertools
import traceback
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())


warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def get_assets_metadata(vault_v2: list) -> dict:
    registry_v2_adapter = Contract(web3.ens.resolve("lens.ychad.eth"))
    addresses = [str(vault.vault) for vault in vault_v2]
    assets_dynamic_data = registry_v2_adapter.assetsDynamic(addresses)
    assets_metadata = {}
    for datum in assets_dynamic_data:
        assets_metadata[datum[0]] = datum[-1]
    return assets_metadata


def write_json(json_dict: dict, path: str):
    try:
        with open(path, "w+") as f:
            json.dump(json_dict, f)
    except Exception as error:
        logger.info(f'failed to write {path}')
        logger.error(error)


def main():
    samples = get_samples()

    special = [YveCRVJar(), Backscratcher()]
    registry_v1 = RegistryV1()
    registry_v2 = RegistryV2()

    assets_metadata = get_assets_metadata(registry_v2.vaults)

    loanscan_vault_symbols = []
    loanscan_vault_json = []
    for vault in itertools.chain(special, registry_v1.vaults, registry_v2.vaults):
        try:
            vault_not_endorsed = not (
                hasattr(vault, "is_endorsed") and vault.is_endorsed)
            if vault_not_endorsed:
                continue

            current_vault_address = str(vault.vault)
            next_vault_address = assets_metadata[current_vault_address][2]
            vault_not_migrated = current_vault_address != next_vault_address
            if vault_not_migrated:
                continue

            apy = vault.apy(samples)
            lend_rate_apy = apy.net_apy
            lend_rate_apr = ((apy.net_apy + 1)**(1/365) - 1) * 365
            lend_rates = []
            if apy.type == 'crv':
                for curve_pool_token_address in curve.get_underlying_coins(vault.token):
                    lend_rates.append({
                        "apr": lend_rate_apr,
                        "apy": lend_rate_apy,
                        "tokenSymbol": Contract(curve_pool_token_address).symbol()
                    })
            else:
                vault_token_symbol = vault.token.symbol() if hasattr(
                    vault.token, "symbol") else None
                lend_rates.append({
                    "apr": lend_rate_apr,
                    "apy": lend_rate_apy,
                    "tokenSymbol": vault_token_symbol
                })
            vault_symbol = vault.vault.symbol()
            loanscan_vault_symbols.append(vault_symbol)
            loanscan_vault_json.append({
                "symbol": vault_symbol,
                "lendRates": lend_rates
            })
        except Exception as error:
            logger.info(
                f'failed to reduce loanscan lendRate for vault {str(vault.vault)} {vault.vault.symbol()}')
            logger.error(error)

    out_path = "generated"
    loanscan_path = os.path.join(out_path, "loanscan")
    os.makedirs(out_path, exist_ok=True)
    if os.path.isdir(loanscan_path):
        shutil.rmtree(loanscan_path)
    os.makedirs(loanscan_path, exist_ok=True)

    write_json(loanscan_vault_symbols, os.path.join(loanscan_path, "manifest"))
    write_json(loanscan_vault_json, os.path.join(loanscan_path, "all"))
    for loanscan_vault in loanscan_vault_json:
        write_json({
            "lendRates": loanscan_vault["lendRates"]
        }, os.path.join(loanscan_path, loanscan_vault["symbol"]))

    aws_bucket = os.environ.get("AWS_BUCKET")
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("AWS_ACCESS_SECRET")
    )

    for loanscan_json_filename in os.listdir(loanscan_path):
        try:
            file_path = os.path.join(loanscan_path, loanscan_json_filename)
            s3.upload_file(
                os.path.join(file_path),
                aws_bucket,
                loanscan_json_filename,
                ExtraArgs={
                    'ContentType': "application/json",
                    'CacheControl': "max-age=1800"
                }
            )
        except Exception as error:
            logger.info(f'failed to upload {file_path} to s3')
            logger.error(error)


def with_monitoring():
    from telegram.ext import Updater

    private_group = os.environ.get('TG_YFIREBOT_GROUP_INTERNAL')
    public_group = os.environ.get('TG_YFIREBOT_GROUP_EXTERNAL')
    updater = Updater(os.environ.get('TG_YFIREBOT'))
    now = datetime.now()
    message = f"`[{now}]`\n⚙️ Loanscan API is updating..."
    ping = updater.bot.send_message(
        chat_id=private_group, text=message, parse_mode="Markdown")
    ping = ping.message_id
    try:
        main()
    except Exception as error:
        tb = traceback.format_exc()
        now = datetime.now()
        message = f"`[{now}]`\n🔥 Loanscan API update failed!\n```\n{tb}\n```"
        updater.bot.send_message(
            chat_id=private_group, text=message, parse_mode="Markdown", reply_to_message_id=ping)
        updater.bot.send_message(chat_id=public_group,
                                 text=message, parse_mode="Markdown")
        raise error
    message = "✅ Loanscan API update successful!"
    updater.bot.send_message(
        chat_id=private_group, text="✅ Loanscan API update successful!", reply_to_message_id=ping)
