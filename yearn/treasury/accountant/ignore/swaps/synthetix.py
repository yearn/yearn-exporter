
from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import HashMatcher


def is_synthetix_swap(tx: TreasuryTx) -> bool:
    # TODO Figure out hueristics for sorting these if they become more frequent
    return tx in HashMatcher({
        Network.Mainnet: [
            "0x5a55121911d9a3992fc1ea9504da9b86331da2148822d88c16f805b2c6b2c753",
        ]
    }.get(chain.id, []))
