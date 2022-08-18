
from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import HashMatcher


def is_airdrop(tx: TreasuryTx) -> bool:
    hashes = {
        Network.Mainnet: [
            "0x327684dab9e3ce61d125b36fe0b59cbfbc8aa5ac7a5b051125ab7cac3b93b90b",
        ],
    }.get(chain.id, [])
    return tx in HashMatcher(hashes)