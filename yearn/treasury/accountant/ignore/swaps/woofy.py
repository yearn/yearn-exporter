from decimal import Decimal

from brownie import ZERO_ADDRESS
from yearn.constants import YFI
from yearn.entities import TreasuryTx

WOOFY = "0xD0660cD418a64a1d44E9214ad8e459324D8157f1"
YFI_SCALE = Decimal(10) ** 18
WOOFY_SCALE = Decimal(10) ** 12


def is_woofy(tx: TreasuryTx) -> bool:
    """ Returns True if the tx involved wrapping or unwrapping WOOFY. """
    
    # Wrapping, YFI side
    if tx.to_address == WOOFY and tx._symbol == "YFI" and "Transfer" in tx._events:
        # Check for WOOFY transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != WOOFY:
                continue
            sender, receiver, amount = transfer.values()
            if sender == ZERO_ADDRESS and tx.from_address == receiver and Decimal(amount) / YFI_SCALE == tx.amount:
                return True

    # Wrapping, WOOFY side
    elif tx.from_address == ZERO_ADDRESS and tx._symbol == "WOOFY" and "Transfer" in tx._events:
        # Check for YFI transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != YFI:
                continue
            sender, receiver, amount = transfer.values()
            if receiver == WOOFY and tx.to_address == sender and Decimal(amount) / WOOFY_SCALE == tx.amount:
                return True
    
    # Unwrapping, YFI side
    elif tx.from_address == WOOFY and tx._symbol == "YFI" and "Transfer" in tx._events:
        # Check for WOOFY transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != WOOFY:
                continue
            sender, receiver, amount = transfer.values()
            if tx.to_address == sender and receiver == ZERO_ADDRESS and Decimal(amount) / YFI_SCALE == tx.amount:
                return True

    # Unwrapping, WOOFY side
    elif tx.to_address == ZERO_ADDRESS and tx._symbol == "WOOFY" and "Transfer" in tx._events:
        # Check for YFI transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != YFI:
                continue
            sender, receiver, amount = transfer.values()
            if sender == WOOFY and tx.from_address == receiver and Decimal(amount) / WOOFY_SCALE == tx.amount:
                return True
    return False
