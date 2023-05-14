from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_idle_withdrawal(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0xd1e7b71b967648aab5f4cbcca2f565faf5f7348a1ccc59752ca947c2cc335035",
    ])