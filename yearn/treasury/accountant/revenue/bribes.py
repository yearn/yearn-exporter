
from yearn.entities import TreasuryTx

def is_ycrv_bribe(tx: TreasuryTx) -> bool:
    return tx._from_nickname == "Contract: BribeSplitter"

def is_ybribe_fees(tx: TreasuryTx) -> bool:
    return False
