from brownie import config, Wei, Contract, chain, accounts, VaultsRegistryHelper
import requests

def main():
    wavey = accounts.load('wavey')
    # ycrv = wavey.deploy(
    #     StrategyProxy,
    #     publish_source=True
    # )

    strat = wavey.deploy(
        VaultsRegistryHelper,
        '0x1ba4eB0F44AB82541E56669e18972b0d6037dfE0', # Registry
        publish_source=True
    )