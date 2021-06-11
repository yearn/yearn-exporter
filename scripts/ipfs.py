import dataclasses
import itertools
import warnings
import logging
import shutil
import json
import os

from typing import Union
from time import time
from yearn.special import Backscratcher, YveCRVJar

import ipfshttpclient
import requests
import boto3

from brownie import Contract
from brownie.exceptions import BrownieEnvironmentWarning

from yearn.apy import get_samples, ApySamples
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault as VaultV2

from yearn.utils import contract_creation_block
from yearn.prices import magic

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")

ICON = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/%s/logo-128.png"


def wrap_vault(vault: Union[VaultV1, VaultV2], samples: ApySamples, aliases: dict) -> dict:
    apy = vault.apy(samples)
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
    
    token_alias = aliases[str(vault.token)]["name"] if str(vault.token) in aliases else vault.token.symbol()
    vault_alias = aliases[str(vault.vault)]["name"] if str(vault.vault) in aliases else token_alias

    tvl = vault.tvl()

    return {
        "inception": inception,
        "address": str(vault.vault),
        "symbol": vault.symbol if hasattr(vault, "symbol") else vault.vault.symbol(),
        "name": vault.name,
        "display_name": vault_alias,
        "icon": ICON % str(vault.vault),
        "token": {
            "name": vault.token.name() if hasattr(vault.token, "name") else vault.token._name,
            "symbol": vault.token.symbol() if hasattr(vault.token, "symbol") else None,
            "address": str(vault.token),
            "decimals": vault.token.decimals() if hasattr(vault.token, "decimals") else None,
            "display_name": token_alias,
            "icon": ICON % str(vault.token),
            "price": tvl.price,
        },
        "tvl": dataclasses.asdict(tvl),
        "apy": dataclasses.asdict(apy),
        "fees": dataclasses.asdict(apy.fees),
        "strategies": strategies,
        "endorsed": vault.is_endorsed if hasattr(vault, "is_endorsed") else True,
        "version": vault.api_version if hasattr(vault, "api_version") else "0.1",
        "decimals": vault.decimals if hasattr(vault, "decimals") else vault.vault.decimals(),
        "type": "v2" if isinstance(vault, VaultV2) else "v1",
        "emergency_shutdown": vault.vault.emergencyShutdown() if hasattr(vault.vault, "emergencyShutdown") else False,
        "tags": [],
        "updated": int(time()),
    }


def main():
    ipfs_address = os.environ.get("IPFS_NODE_ADDRESS")
    ipfs_key = os.environ.get("IPFS_NODE_KEY")
    ipfs_secret = os.environ.get("IPFS_NODE_SECRET")

    client = ipfshttpclient.connect(ipfs_address, auth=(ipfs_key, ipfs_secret))
    print(f"Connected to IPFS node id: {client.id()}")

    data = []

    aliases_url = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/aliases.json"
    aliases = requests.get(aliases_url).json()
    aliases = {alias["address"]: alias for alias in aliases}

    samples = get_samples()

    special = [YveCRVJar(), Backscratcher()]
    v1_registry = RegistryV1()
    v2_registry = RegistryV2()

    for vault in itertools.chain(special, v1_registry.vaults, v2_registry.vaults):
        try:
            data.append(wrap_vault(vault, samples, aliases))
        except ValueError as error:
            logger.error(error)

    out = "generated"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    keep = os.path.join(out, ".keep")
    with open(keep, 'a'):
        try:
            os.utime(keep, None)
        except OSError:
            pass

    prefix = os.path.join(out, "v1", "chains", "1")
    os.makedirs(prefix, exist_ok=True)

    ns_vaults = os.path.join(prefix, "vaults")
    os.makedirs(ns_vaults, exist_ok=True)

    for vault in data:
        with open(os.path.join(ns_vaults, vault["address"]), "w+") as f:
            json.dump(vault, f)

    with open(os.path.join(ns_vaults, "all"), "w+") as f:
        json.dump(data, f)

    uploads = client.add(out, recursive=True)

    print(f"Uploaded \"{out}\"")
    for upload in uploads:
        if upload["Name"] == out:
            hash = upload["Hash"]
            size = upload["Size"]
            print(f"- Hash: {hash}")
            print(f"- Size: {size} bytes")

    dnslink = f"\"dnslink=/ipfs/{hash}\""

    aws_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret = os.environ.get("AWS_ACCESS_SECRET")
    aws_zone_id = os.environ.get("AWS_ZONE_ID")
    aws_zone_record = os.environ.get("AWS_ZONE_RECORD")

    dns = boto3.client(
        "route53", 
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret
    )
    try:
        dns.change_resource_record_sets(
            HostedZoneId=aws_zone_id,
            ChangeBatch={
                'Comment': dnslink,
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': aws_zone_record,
                            'Type': 'TXT',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': dnslink}],
                        },
                    }
                ],
            },
        )
    except Exception as error:
        print(error)