
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher, IterFilter


def is_gearbox_deposit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x5666b03add778468482fb376e65761128f9f5051b487f3efc996a55c3620d6d4", IterFilter('log_index', [366, 367])],
        ["0x9e113dda11fcd758df2fe94a641aa7afe6329afec4097a8cb5d6fb68489cf7d8", IterFilter('log_index', [74, 75])],
    ])
    
def is_gearbox_withdrawal(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0xb98d8f4dd3d9de50e6fec700fb8e5a732e5a564b7edfe365f97e601694536bb5",
        ["0x1d9e7930d0bf6725a4ffff43e284dfa9d10e34e16460e75d01a7f05a98e252a6", IterFilter('log_index', [212, 213])],
    ])
    