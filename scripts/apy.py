import warnings
import logging

from semantic_version import Version

from brownie.exceptions import BrownieEnvironmentWarning

from tabulate import tabulate

from yearn import v2, v1, apy
from yearn.prices.curve import is_curve_lp_token

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yearn.apy")


def main():
    data = []

    samples = apy.get_samples()

    v1_registry = v1.registry.Registry()

    for vault in v1_registry.vaults:
        if is_curve_lp_token(vault.token.address):
            vault_apy = apy.curve.simple(vault, samples)
        else:
            vault_apy = apy.v1.simple(vault, samples)
        data.append({"product": vault_apy.type, "name": vault.name, "apy": vault_apy.net_apy})

    v2_registry = v2.registry.Registry()

    for vault in v2_registry.vaults:
        try:
            if is_curve_lp_token(vault.token.address):
                vault_apy = apy.curve.simple(vault, samples)
            elif Version(vault.api_version) >= Version("0.3.2"):
                vault_apy = apy.v2.average(vault, samples)
            else:
                vault_apy = apy.v2.simple(vault, samples)
            data.append({"product": vault_apy.type, "name": vault.name, "apy": vault_apy.net_apy})
        except apy.ApyError as error:
            logger.error(error)
        except Exception as error:
            print(vault)
            raise error

    data.sort(key=lambda x: -x["apy"])
    print(tabulate(data, floatfmt=",.0%"))
