
from brownie import ZERO_ADDRESS
from y import Contract

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury


def is_aave_deposit(tx: TreasuryTx) -> bool:
    # Atoken side

    # Underlying side
    pass

def is_aave_withdrawal(tx: TreasuryTx) -> bool:
    # Atoken side
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == ZERO_ADDRESS and "RedeemUnderlying" in tx._events and hasattr(Contract(tx.token.address.address), 'underlyingAssetAddress'):
        for event in tx._events['RedeemUnderlying']:
            if (
                event['_user'] == tx.from_address.address and
                Contract(tx.token.address.address).underlyingAssetAddress() == event['_reserve'] and
                round(event['_amount'] / tx.token.scale, 15) == round(float(tx.amount), 15)
            ):
                return True


    # Underlying side
    if tx.to_address and tx.to_address.address in treasury.addresses and "RedeemUnderlying" in tx._events:
        for event in tx._events['RedeemUnderlying']:
            if (
                tx.token.address.address == event['_reserve'] and
                event['_user'] == tx.to_address.address and
                round(event['_amount'] / tx.token.scale, 15) == round(float(tx.amount), 15)
            ):
                return True
    
    # TODO: If these end up becoming more frequent, figure out sorting hueristics.
    return tx in HashMatcher(["0x36ee5631859a15f57b44e41b8590023cf6f0c7b12d28ea760e9d8f8003f4fc50"])
