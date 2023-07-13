import dataclasses
import json

import sentry_sdk
from brownie import chain
from multicall.utils import await_awaitable
from y.networks import Network

from yearn.apy import get_samples
from yearn.v2.vaults import Vault as VaultV2

sentry_sdk.set_tag('script','fantom_apy')

def wftm():
    fetch_apy("0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0")
    
def yfi():
    fetch_apy("0x2C850cceD00ce2b14AA9D658b7Cad5dF659493Db")

def dai():
    fetch_apy("0x637eC617c86D24E421328e6CAEa1d92114892439")

def usdc():
    fetch_apy("0xEF0210eB96c7EB36AF8ed1c20306462764935607")

def mim():
    fetch_apy("0x0A0b23D9786963DE69CB2447dC125c49929419d8")

def fetch_apy(vault_address):
    if chain.id != Network.Fantom:
        raise Exception("run on fantom")
    samples = get_samples()
    vault = VaultV2.from_address(vault_address)
    print(json.dumps(dataclasses.asdict(await_awaitable(vault.apy(samples))), indent=2))
