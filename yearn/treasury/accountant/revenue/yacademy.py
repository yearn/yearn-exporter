
from yearn.entities import TreasuryTx

YACADEMY_SPLIT_CONTRACT = "0x2ed6c4B5dA6378c7897AC67Ba9e43102Feb694EE"

def is_yacademy_audit_revenue(tx: TreasuryTx) -> bool:
    return tx.from_address.address == YACADEMY_SPLIT_CONTRACT or tx.hash == "0x6e4f4405bd0970d42a48795a5219c14c763705f6ea9879affea652438758c065"
