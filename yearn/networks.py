from enum import IntEnum


class Network(IntEnum):
    Mainnet = 1
    Fantom = 250
    Arbitrum = 42161

    @staticmethod
    def label(chain_id):
        if chain_id == Network.Mainnet:
            return "ETH"
        elif chain_id == Network.Fantom:
            return "FTM"
        elif chain_id == Network.Arbitrum:
            return "ARRB"
