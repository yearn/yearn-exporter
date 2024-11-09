
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher

# NOTE: These predate the yteam revshare splitting implementation so were done manually

def is_yaudit_revshare(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([["0xdf3e6cf2e50052e4eeb57fb2562b5e1b02701014ce65b60e6c8a850c409b341a", Filter('log_index', 127)]])

def is_ylockers_revshare(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([["0x038aeb3351b762bc92c5e4274c01520ae08dc314e2282ececc2a19a033d994a8", Filter('log_index', 163)]])
