
from brownie import chain
from y import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_otc(tx: TreasuryTx) -> bool:
    return tx in HashMatcher({
        Network.Mainnet: [
            "0xd59dfba383c0a7d5f0e30124888fa6d9c2c964755fb9bed8f22483feb292c1e9",
            "0xa00430b408c75dc432fcc0bbcabc5c3c63196addab532eecd233f6e80b295990",

            "0x3419d8378321b5cb59c69584693ef59a65aeee4591e7e96c31f31906bc9a627a",
            "0x30afed767aafd21696242c6a54576afc6598e976b969ffe50591360c729ef35a",
        ],
    }.get(chain.id, []))
