import json
import dataclasses
import warnings
import logging

from brownie.exceptions import BrownieEnvironmentWarning

from tabulate import tabulate

from yearn.apy import get_samples, ApyError
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

from yearn.v2.vaults import Vault as VaultV2
from yearn.v2.strategies import Strategy as StrategyV2

from yearn.special import Backscratcher, YveCRVJar

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def main():
    data = []

    samples = get_samples()

    v1_registry = RegistryV1()

    for vault in v1_registry.vaults:
        apy = vault.apy(samples)
        data.append({"product": apy.type, "name": vault.name, "apy": apy.net_apy})

    v2_registry = RegistryV2()

    for vault in v2_registry.vaults:
        try:
            apy = vault.apy(samples)
            data.append({"product": apy.type, "name": vault.name, "apy": apy.net_apy})
        except ApyError as error:
            logger.error(error)
        except Exception as error:
            print(vault)
            raise error

    data.sort(key=lambda x: -x["apy"])
    print(tabulate(data, floatfmt=",.0%"))

def lusd():
    samples = get_samples()
    address = "0x5fA5B62c8AF877CB37031e0a3B2f34A78e3C56A6"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def rai():
    samples = get_samples()
    address = "0x873fB544277FD7b977B196a826459a69E27eA4ea"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))
    
def tricrypto():
    samples = get_samples()
    address = "0x3D980E50508CFd41a13837A60149927a11c03731"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def pickleJar():
    samples = get_samples()
    special = YveCRVJar()
    print(json.dumps(dataclasses.asdict(special.apy(samples)), indent=2))

def mim():
    samples = get_samples()
    address = "0x2DfB14E32e2F8156ec15a2c21c3A6c053af52Be8"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def eurt():
    samples = get_samples()
    address = "0x0d4EA8536F9A13e4FBa16042a46c30f092b06aA5"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def yvboost():
    samples = get_samples()
    address = "0x9d409a0A012CFbA9B15F6D4B36Ac57A46966Ab9a"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))
