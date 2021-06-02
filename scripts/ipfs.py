import dataclasses
import itertools
from sys import api_version
import warnings
import logging
import os

from typing import Union
from yearn.apy.common import ApySamples

import ipfshttpclient

from brownie import Contract
from brownie.exceptions import BrownieEnvironmentWarning

from yearn.apy import ApyError, calculate_apy, get_samples
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault as VaultV2
from yearn.v2.strategies import Strategy as StrategyV2

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


"""
Schema:
{
    "inception": 12484741,
    "icon": "https://raw.githack.com/yearn/yearn-assets/master/icons/tokens/0xA74d4B67b3368E83797a35382AFB776bAAE4F5C8/logo-128.png",
    "symbol": "yvCurve-alUSD",
    "apy": {
        "description": "Pool APY + Boosted CRV APY",
        "type": "curve",
        "data": {
        "totalApy": 0.2259881468188956,
        "netApy": 0.15622599360399536,
        "currentBoost": 2.5,
        "boostedApr": 0.1938560839158244,
        "tokenRewardsApr": 0,
        "poolApy": 0.010304264744043643,
        "baseApr": 0.07754243356632977
        },
        "composite": true,
        "recommended": 0.15622599360399536
    },
    "address": "0xA74d4B67b3368E83797a35382AFB776bAAE4F5C8",
    "strategies": [
        {
        "name": "CurvealUSD3CRV-fVoterProxy",
        "address": "0x31CD90D60516ED18750bA49b2C9d1053190F40d9"
        }
    ],
    "tvl": {
        "totalAssets": 5880149861883790000000000,
        "value": "5910549.706621",
        "price": 1.005169909857933
    },
    "endorsed": true,
    "apiVersion": "0.3.5",
    "name": "Curve alUSD Pool yVault",
    "displayName": "crvALUSD",
    "updated": 1622656321,
    "fees": {
        "special": {
        "keepCrv": 0
        },
        "general": {
        "managementFee": 200,
        "performanceFee": 2000
        }
    },
    "token": {
        "name": "Curve.fi Factory USD Metapool: Alchemix USD",
        "icon": "https://raw.githack.com/yearn/yearn-assets/master/icons/tokens/0x43b4FdFD4Ff969587185cDB6f0BD875c5Fc83f8c/logo-128.png",
        "symbol": "alUSD3CRV-f",
        "address": "0x43b4FdFD4Ff969587185cDB6f0BD875c5Fc83f8c",
        "displayName": "crvALUSD",
        "decimals": 18
    },
    "decimals": 18,
    "emergencyShutdown": false,
    "tags": [],
    "type": "v2"
},
"""

def imerge(a, b):
    for i, j in zip(a,b):
        yield i
        yield j


def wrap_vault(vault: Union[VaultV1, VaultV2], samples: ApySamples) -> dict:
    # apy = calculate_apy(vault, samples)
    if isinstance(vault, VaultV2):
        strategies = [{"address": str(strategy.strategy), "name": strategy.name} for strategy in vault.strategies]
    else:
        strategies = [{"address": str(vault.strategy), "name": vault.strategy.getName() if hasattr(vault.strategy, "getName") else vault.strategy._name}]
    
    return {
        "address": str(vault.vault),
        "symbol": vault.vault.symbol(),
        "strategies": strategies,
        "endorsed": vault.is_endorsed if hasattr(vault, "is_endorsed") else True,
        "apiVersion": vault.api_version if hasattr(vault, "api_version") else "0.1",
        "name": vault.name,
        "decimals": vault.vault.decimals(),
        "emergencyShutdown": vault.vault.emergencyShutdown() if hasattr(vault.vault, "emergencyShutdown") else False,
        "type": "v2" if isinstance(vault, VaultV1) else "v1"
    }


def main():
    # address = os.environ.get("IPFS_NODE_ADDRESS")
    # key = os.environ.get("IPFS_NODE_KEY")
    # secret = os.environ.get("IPFS_NODE_SECRET")

    # client = ipfshttpclient.connect(address, auth=(key, secret))
    # print(client.id())

    data = []

    samples = get_samples()

    v1_registry = RegistryV1()
    v2_registry = RegistryV2()
    for vault in imerge(v1_registry.vaults, v2_registry.vaults):
        try:
            data.append(wrap_vault(vault, samples))
        except ValueError as error:
            logger.error(error)

    print(data)
