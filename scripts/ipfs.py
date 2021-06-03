import dataclasses
import warnings
import logging
import json
import os

from typing import Union
from time import time

import ipfshttpclient
import requests

from brownie import Contract
from brownie.exceptions import BrownieEnvironmentWarning

from yearn.apy import calculate_apy, get_samples, ApySamples
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault as VaultV2

from yearn.utils import contract_creation_block
from yearn.prices import magic

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def imerge(a, b):
    for i, j in zip(a,b):
        yield i
        yield j

ICON = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/%s/logo-128.png"

def wrap_vault(vault: Union[VaultV1, VaultV2], samples: ApySamples, aliases: dict) -> dict:
    apy = calculate_apy(vault, samples)
    if isinstance(vault, VaultV2):
        strategies = [{"address": str(strategy.strategy), "name": strategy.name} for strategy in vault.strategies]
    else:
        strategies = [{"address": str(vault.strategy), "name": vault.strategy.getName() if hasattr(vault.strategy, "getName") else vault.strategy._name}]
    inception = contract_creation_block(str(vault.vault))
    total_assets = vault.vault.totalAssets() if hasattr(vault.vault, "totalAssets") else vault.vault.balance()
    try:
        price = magic.get_price(vault.token)
    except magic.PriceError:
        price = None
    token_alias = aliases[str(vault.token)]["name"] if str(vault.token) in aliases else vault.token.symbol()
    vault_alias = aliases[str(vault.vault)]["name"] if str(vault.vault) in aliases else token_alias

    tvl = total_assets * price / 10 ** vault.vault.decimals() if price else None

    return {
        "inception": inception,
        "address": str(vault.vault),
        "symbol": vault.vault.symbol(),
        "name": vault.name,
        "displayName": vault_alias, 
        "icon": ICON % str(vault.vault),
        "token": {
            "name": vault.token.name() if hasattr(vault.token, "name") else vault.token._name,
            "symbol": vault.token.symbol() if hasattr(vault.token, "symbol") else None,
            "address": str(vault.token),
            "decimals": vault.token.decimals() if hasattr(vault.token, "decimals") else None,
            "displayName": token_alias, 
            "icon": ICON % str(vault.token),
            "price": price
        },
        "tvl": {
            "totalAssets": total_assets,
            "value": tvl 
        },
        "apy": dataclasses.asdict(apy),
        "fees": dataclasses.asdict(apy.fees),
        "strategies": strategies,
        "endorsed": vault.is_endorsed if hasattr(vault, "is_endorsed") else True,
        "apiVersion": vault.api_version if hasattr(vault, "api_version") else "0.1",
        "decimals": vault.vault.decimals(),
        "type": "v2" if isinstance(vault, VaultV1) else "v1",
        "emergencyShutdown": vault.vault.emergencyShutdown() if hasattr(vault.vault, "emergencyShutdown") else False,
        "tags": [],
        "updated": int(time()),
    }


def main():
    # address = os.environ.get("IPFS_NODE_ADDRESS")
    # key = os.environ.get("IPFS_NODE_KEY")
    # secret = os.environ.get("IPFS_NODE_SECRET")

    # client = ipfshttpclient.connect(address, auth=(key, secret))
    # print(client.id())

    data = []

    aliases_url = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/aliases.json" 
    aliases = requests.get(aliases_url).json()
    aliases = {alias["address"]: alias for alias in aliases}

    samples = get_samples()

    v1_registry = RegistryV1()
    v2_registry = RegistryV2()

    for vault in imerge(v1_registry.vaults, v2_registry.vaults):
        try:
            data.append(wrap_vault(vault, samples, aliases))
        except ValueError as error:
            logger.error(error)

    print(json.dumps(data))
