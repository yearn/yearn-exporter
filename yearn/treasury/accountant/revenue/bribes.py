
from yearn.entities import TreasuryTx

def is_ycrv_bribe(tx: TreasuryTx) -> bool:
    return tx._from_nickname in [
        # OLD
        "Contract: BribeSplitter",
        # NEW
        "Contract: YCRVSplitter",
        # done manually during migration
    ] or tx.hash == "0x3c635388812bed82845c0df3531583399fdf736ccfb95837b362379766955f2d"

def is_ybribe_fees(tx: TreasuryTx) -> bool:
    return False
