import warnings
import logging

from brownie.exceptions import BrownieEnvironmentWarning

from tabulate import tabulate

from yearn.apy import calculate_apy, get_samples, ApyError
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
        apy = calculate_apy(vault, samples)
        data.append({"product": apy.type, "name": vault.name, "apy": apy.net_apy})

    v2_registry = RegistryV2()

    for vault in v2_registry.vaults:
        try:
            apy = calculate_apy(vault, samples)
            data.append({"product": apy.type, "name": vault.name, "apy": apy.net_apy})
        except ApyError as error:
            logger.error(error)
        except Exception as error:
            print(vault)
            raise error

    data.sort(key=lambda x: -x["apy"])
    print(tabulate(data, floatfmt=",.0%"))

def yvboost():
    samples = get_samples()
    address = "0x9d409a0A012CFbA9B15F6D4B36Ac57A46966Ab9a"
    vault = VaultV2.from_address(address)
    vault.load_strategies()
    vault._strategies["0x9d409a0A012CFbA9B15F6D4B36Ac57A46966Ab9a"] = StrategyV2("0x9d409a0A012CFbA9B15F6D4B36Ac57A46966Ab9a", vault)
    vault._strategies["0x683b5C88D48FcCfB3e778FF0fA954F84cA7Ce9DF"] = StrategyV2("0x683b5C88D48FcCfB3e778FF0fA954F84cA7Ce9DF", vault)
    print(calculate_apy(vault, samples))