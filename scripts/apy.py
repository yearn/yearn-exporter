import dataclasses
import json
import logging
import warnings

import sentry_sdk
from brownie.exceptions import BrownieEnvironmentWarning
from tabulate import tabulate

from yearn import logs
from yearn.apy import ApyError, get_samples
from yearn.special import Backscratcher, YveCRVJar
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2
from yearn.v2.strategies import Strategy as StrategyV2
from yearn.v2.vaults import Vault as VaultV2

sentry_sdk.set_tag('script','apy')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)

logs.basicConfig(level=logging.DEBUG)
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


def calculate_apy(address):
    samples = get_samples()
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))


def pickleJar():
    samples = get_samples()
    special = YveCRVJar()
    print(json.dumps(dataclasses.asdict(special.apy(samples)), indent=2))


def lusd():
    calculate_apy("0x5fA5B62c8AF877CB37031e0a3B2f34A78e3C56A6")


def rai():
    calculate_apy("0x873fB544277FD7b977B196a826459a69E27eA4ea")


def tricrypto():
    calculate_apy("0x3D980E50508CFd41a13837A60149927a11c037")


def mim():
    calculate_apy("0x2DfB14E32e2F8156ec15a2c21c3A6c053af52Be8")


def eurt():
    calculate_apy("0x0d4EA8536F9A13e4FBa16042a46c30f092b06aA5")


def yvboost():
    calculate_apy("0x9d409a0A012CFbA9B15F6D4B36Ac57A46966Ab9a")


def ibeur():
    calculate_apy("0x67e019bfbd5a67207755D04467D6A70c0B75bF60")


def cvxcrv():
    calculate_apy("0x4560b99C904aAD03027B5178CCa81584744AC01f")


def ibjpy():
    calculate_apy("0x59518884EeBFb03e90a18ADBAAAB770d4666471e")


def ibkrw():
    calculate_apy("0x528D50dC9a333f01544177a924893FA1F5b9F748")


def yfi():
    calculate_apy("0xdb25cA703181E7484a155DD612b06f57E12Be5F0")


def sushi():
    calculate_apy("0x6d765CbE5bC922694afE112C140b8878b9FB0390")


def ibgbp():
    calculate_apy("0x595a68a8c9D5C230001848B69b1947ee2A607164")


def dai():
    calculate_apy("0xdA816459F1AB5631232FE5e97a05BBBb94970c95")


def old_dai():
    calculate_apy("0x19D3364A399d251E894aC732651be8B0E4e85001")

def eurs_usdc():
    calculate_apy("0x801Ab06154Bf539dea4385a39f5fa8534fB53073")

def crv_eth():
    calculate_apy("0x6A5468752f8DB94134B6508dAbAC54D3b45efCE6")

def mim_crv():
    calculate_apy("0xA97E7dA01C7047D6a65f894c99bE8c832227a8BC")