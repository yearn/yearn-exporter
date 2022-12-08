
from brownie import ZERO_ADDRESS
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury

MINTER = "0x01D7f32B6E463c96c00575fA97B8224326C6A6B9"
ZAP = "0x6F3c2647f0C0fBcCbaF74c400D886033F8c6d2E6"

def is_minting_ycrv(tx: TreasuryTx) -> bool:
    # yCRV side
    if tx.from_address.address == ZERO_ADDRESS and tx._symbol == "yCRV" and tx.to_address and tx.to_address.address in treasury.addresses:
        return True
    # Input side
    elif tx._symbol in ["yveCRV-DAO", "yvBOOST"] and tx.to_address and tx.to_address.address in [MINTER, ZAP]:
        return True
