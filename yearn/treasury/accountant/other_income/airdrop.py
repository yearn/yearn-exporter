
from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import HashMatcher


def is_airdrop(tx: TreasuryTx) -> bool:
    hashes = {
        Network.Mainnet: [
            "0x327684dab9e3ce61d125b36fe0b59cbfbc8aa5ac7a5b051125ab7cac3b93b90b",
            "0x3424e8a6688c89f7974968213c8c25f3bd8100f78c54475edb001c11a8ad5d21", # Gnosis SAFE airdrop
            "0x44f7d3b2030799ea45932baf6049528a059aabd6387f3128993d646d01c8e877", # TKX
            "0xf2dbe58dffd3bc1476755e9f74e2ae07531579d0a3ea9e2aaac2ef902e080c2a", # TKX
        ],
    }.get(chain.id, [])
    return tx in HashMatcher(hashes)