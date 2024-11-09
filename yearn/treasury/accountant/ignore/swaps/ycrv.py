
from brownie import ZERO_ADDRESS
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury

MINTER = "0x01D7f32B6E463c96c00575fA97B8224326C6A6B9"
ZAP = "0x6F3c2647f0C0fBcCbaF74c400D886033F8c6d2E6"
YCRV = "0x4c1317326fD8EFDeBdBE5e1cd052010D97723bd6"

def is_minting_ycrv(tx: TreasuryTx) -> bool:
    """Includes all ycrv wrappers""" 
    old_wrappers = ["yveCRV-DAO", "yvBOOST"]
    new_wrappers = ["st-yCRV","lp-yCRV"]
    # Zapping old-to-new
    # yCRV side
    if tx.from_address == ZERO_ADDRESS and tx._symbol == "yCRV" and tx.to_address.address in treasury.addresses:
        return True
    # Input side
    elif tx._symbol in old_wrappers and tx.to_address in [MINTER, ZAP, YCRV]:
        return True
    
    # wrapping wrappers
    # wrapper side
    elif tx._symbol in new_wrappers and tx.from_address == ZERO_ADDRESS:
        return True
    
    # yCRV side
    elif tx._symbol == "yCRV" and tx.to_address == ZAP:
        return True
    
    # unwrapping wrappers
    # wrapper side
    elif tx._symbol in new_wrappers and tx.to_address == ZAP:
        return True
    
    # yCRV side
    elif tx._symbol == "yCRV" and tx.from_address == ZAP:
        return True
    
    # NOTE: Crossing between wrappers is captured by the above logic as well
    
    return False
