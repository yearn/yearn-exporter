import json
import dataclasses
from yearn.apy import get_samples
from yearn.v2.vaults import Vault as VaultV2

def wftm():
    samples = get_samples()
    address = "0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))
    
def yfi():
    samples = get_samples()
    address = "0x2C850cceD00ce2b14AA9D658b7Cad5dF659493Db"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def dai():
    samples = get_samples()
    address = "0x637eC617c86D24E421328e6CAEa1d92114892439"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def usdc():
    samples = get_samples()
    address = "0xEF0210eB96c7EB36AF8ed1c20306462764935607"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))

def mim():
    samples = get_samples()
    address = "0x0A0b23D9786963DE69CB2447dC125c49929419d8"
    vault = VaultV2.from_address(address)
    print(json.dumps(dataclasses.asdict(vault.apy(samples)), indent=2))