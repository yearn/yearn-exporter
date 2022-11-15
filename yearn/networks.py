from enum import IntEnum

from brownie import chain

from yearn.exceptions import UnsupportedNetwork


class Network(IntEnum):
    Mainnet = 1
    Gnosis = 100
    Fantom = 250
    Arbitrum = 42161
    Optimism = 10
    Goerli = 5

    @staticmethod
    def label(chain_id: int = None):
        if chain_id is None:
            chain_id = chain.id

        if chain_id == Network.Mainnet:
            return "ETH"
        elif chain_id == Network.Gnosis:
            return "GNO"
        elif chain_id == Network.Fantom:
            return "FTM"
        elif chain_id == Network.Arbitrum:
            return "ARRB"
        elif chain_id == Network.Optimism:
            return "OPT"
        elif chain_id == Network.Goerli:
            return "GTH"
        else:
            raise UnsupportedNetwork(
                f'chainid {chain_id} is not currently supported. Please add network details to yearn-exporter/yearn/networks.py'
            )
