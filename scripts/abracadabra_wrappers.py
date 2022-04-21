import sentry_sdk
from brownie import *
from rich import print
from yearn.partners.snapshot import BentoboxWrapper
from yearn.utils import contract
from yearn.v2.registry import Registry

sentry_sdk.set_tag('script','abracadabra_wrappers')

# https://docs.abracadabra.money/our-ecosystem/our-cauldrons-contract
CAULDRONS = [
    '0x7b7473a76D6ae86CE19f7352A1E89F6C9dc39020',
    '0x806e16ec797c69afa8590A55723CE4CC1b54050E',
    '0x05500e2Ee779329698DF35760bEdcAAC046e7C27',
    '0x003d5A75d284824Af736df51933be522DE9Eed0f',
    '0x98a84EfF6e008c5ed0289655CcdCa899bcb6B99F',
    '0xEBfDe87310dc22404d918058FAa4D56DC4E93f0A',
    '0x0BCa8ebcB26502b013493Bf8fE53aA2B1ED401C1',
    '0x6cbAFEE1FaB76cA5B5e144c43B3B50d42b7C8c8f',
    '0x551a7CfF4de931F32893c928bBc3D25bF1Fc5147',
    '0x920D9BD936Da4eAFb5E25c6bDC9f6CB528953F9f',
    '0xFFbF4892822e0d552CFF317F65e1eE7b5D3d9aE6',
    '0xC319EEa1e792577C319723b5e60a15dA3857E7da',
    '0x4EAeD76C3A388f4a841E9c765560BBe7B3E4B3A0',
    '0x6Ff9061bB8f97d948942cEF376d98b51fA38B91f',
    '0xbb02A884621FB8F5BFd263A67F58B65df5b090f3',
    '0xf179fe36a36B32a4644587B8cdee7A23af98ed37',
    '0x7Ce7D9ED62B9A6c5aCe1c6Ec9aeb115FA3064757'
]


def main():
    v2 = Registry()
    vaults = [str(vault.vault) for vault in v2.vaults]
    wrappers = []
    for cauldron in CAULDRONS:
        collateral = contract(cauldron).collateral()
        if collateral not in vaults:
            continue
        wrappers.append(
            BentoboxWrapper(
                name=Contract(collateral).symbol(),
                vault=collateral,
                wrapper=cauldron,
            )
        )
    print(wrappers)
