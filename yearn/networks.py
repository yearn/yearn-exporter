from enum import IntEnum

from brownie import chain

from yearn.exceptions import UnsupportedNetwork


class Network(IntEnum):
    Mainnet = 1
    Gnosis = 100
    Fantom = 250
    Arbitrum = 42161

    @staticmethod
    def label(chain_id: int = None):
        if chain_id is None:
            chain_id = chain.id

        if chain_id == Network.Mainnet:
            return "ETH"
        elif chain_id == Network.Gnosis:
            return "XDAI"
        elif chain_id == Network.Fantom:
            return "FTM"
        elif chain_id == Network.Arbitrum:
            return "ARRB"
        else:
            raise UnsupportedNetwork(
                f'chainid {chain_id} is not currently supported. Please add network details to yearn-exporter/yearn/networks.py'
            )
