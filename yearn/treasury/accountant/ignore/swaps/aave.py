
from decimal import Decimal

from brownie import ZERO_ADDRESS

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury


def is_aave_deposit(tx: TreasuryTx) -> bool:
    # Atoken side

    # Underlying side
    # TODO we didnt need this historically??
    return False

def is_aave_withdrawal(tx: TreasuryTx) -> bool:
    # Atoken side
    if tx.from_address.address in treasury.addresses and tx.to_address == ZERO_ADDRESS and "RedeemUnderlying" in tx._events and hasattr(tx.token.contract, 'underlyingAssetAddress'):
        for event in tx._events['RedeemUnderlying']:
            if (
                tx.from_address == event['_user'] and
                tx.token.contract.underlyingAssetAddress() == event['_reserve'] and
                Decimal(event['_amount']) / tx.token.scale == tx.amount
            ):
                return True


    # Underlying side
    if tx.to_address.address in treasury.addresses and "RedeemUnderlying" in tx._events:
        for event in tx._events['RedeemUnderlying']:
            if tx.token == event['_reserve'] and tx.to_address == event['_user'] and Decimal(event['_amount']) / tx.token.scale == tx.amount:
                return True
    
    # TODO: If these end up becoming more frequent, figure out sorting hueristics.
    return tx in HashMatcher(["0x36ee5631859a15f57b44e41b8590023cf6f0c7b12d28ea760e9d8f8003f4fc50"])
