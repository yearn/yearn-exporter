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
    if tx.to_address and tx.to_address.address == WOOFY and tx._symbol == "YFI" and "Transfer" in tx._events:
        # Check for WOOFY transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != WOOFY:
                continue
            sender, receiver, amount = transfer.values()
            if sender == ZERO_ADDRESS and receiver == tx.from_address.address and amount / YFI_SCALE == tx.amount:
                return True

    # Wrapping, WOOFY side
    elif tx.from_address.address == ZERO_ADDRESS and tx._symbol == "WOOFY" and "Transfer" in tx._events:
        # Check for YFI transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != YFI:
                continue
            sender, receiver, amount = transfer.values()
            if receiver == WOOFY and sender == tx.to_address.address and amount / WOOFY_SCALE == tx.amount:
                return True
    
    # Unwrapping, YFI side
    elif tx.from_address.address == WOOFY and tx._symbol == "YFI" and "Transfer" in tx._events:
        # Check for WOOFY transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != WOOFY:
                continue
            sender, receiver, amount = transfer.values()
            if sender == tx.to_address.address and receiver == ZERO_ADDRESS and amount / YFI_SCALE == tx.amount:
                return True

    # Unwrapping, WOOFY side
    elif tx.to_address and tx.to_address.address == ZERO_ADDRESS and tx._symbol == "WOOFY" and "Transfer" in tx._events:
        # Check for YFI transfer
        for transfer in tx._events["Transfer"]:
            if transfer.address != YFI:
                continue
            sender, receiver, amount = transfer.values()
            if sender == WOOFY and receiver == tx.from_address.address and amount / WOOFY_SCALE == tx.amount:
                return True
