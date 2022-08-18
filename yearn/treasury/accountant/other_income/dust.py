
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_dust_from_positive_slippage(tx: TreasuryTx) -> bool:
    hashes = [
        '0x084d318cc42ea80c19e2c9c321f60b3d6d67274a38eb1c1a58cf0fe4093e9ef8'
    ]
    return tx in HashMatcher(hashes)