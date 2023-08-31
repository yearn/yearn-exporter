
from brownie import chain
from y.networks import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher


def is_airdrop(tx: TreasuryTx) -> bool:
    hashes = {
        Network.Mainnet: [
            "0x327684dab9e3ce61d125b36fe0b59cbfbc8aa5ac7a5b051125ab7cac3b93b90b",
            "0x3424e8a6688c89f7974968213c8c25f3bd8100f78c54475edb001c11a8ad5d21", # Gnosis SAFE airdrop
            "0xb39f2991fdc2c70b43046be3eac36bff35c21c7f66e2888a52afc3956abae451", # Gnosis SAFE airdrop
            "0x4923fd32b4eacdc1617700c67176935676ca4d06bbfbb73644730c55534623db", # Gnosis SAFE airdrop
            ["0xe8b5a4ebf1f04048f6226b22b2865a33621e88ea255dcea0cfd7a975a3a7e387", Filter('log_index', 72)], # Gnosis SAFE airdrop
            "0x44f7d3b2030799ea45932baf6049528a059aabd6387f3128993d646d01c8e877", # TKX
            "0xf2dbe58dffd3bc1476755e9f74e2ae07531579d0a3ea9e2aaac2ef902e080c2a", # TKX
            "0x8079e9cae847da196dc5507561bc9d1434f765f05045bc1a82df735ec83bc6ec", # MTV
        ],
    }.get(chain.id, [])
    return tx in HashMatcher(hashes)