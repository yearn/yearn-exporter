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
    address = "0xA74d4B67b3368E83797a35382AFB776bAAE4F5C8"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))