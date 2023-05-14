
from yearn.entities import TreasuryTx

YACADEMY_SPLIT_CONTRACT = "0x2ed6c4B5dA6378c7897AC67Ba9e43102Feb694EE"

def is_yacademy_audit_revenue(tx: TreasuryTx) -> bool:
    return tx.from_address.address == YACADEMY_SPLIT_CONTRACT
