
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher

def is_yaudit_revshare(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xdf3e6cf2e50052e4eeb57fb2562b5e1b02701014ce65b60e6c8a850c409b341a", Filter('log_index', 127)],
    ])