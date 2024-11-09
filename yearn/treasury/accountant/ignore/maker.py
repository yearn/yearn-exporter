
from decimal import Decimal

from brownie import ZERO_ADDRESS

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury

DEPOSIT_EVENT_ARGS = {"ilk", "usr", "wad"}
WITHDRAWAL_EVENT_ARGS = {"cdp", "dst", "wad"}

def is_yfi_cdp_deposit(tx: TreasuryTx) -> bool:
    if tx._symbol == 'YFI' and tx.from_address.address in treasury.addresses and 'slip' in tx._events:
        for event in tx._events['slip']:
            if all(arg in event for arg in DEPOSIT_EVENT_ARGS) and round(event['wad'] / 1e18, 15) == round(float(tx.amount), 15):
                return True

def is_yfi_cdp_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == 'YFI' and tx.to_address and tx.to_address.address in treasury.addresses and 'flux' in tx._events:
        for event in tx._events['flux']:
            if all(arg in event for arg in WITHDRAWAL_EVENT_ARGS) and round(event['wad'] / 1e18, 15) == round(float(tx.amount), 15):
                return True

def is_usdc_cdp_deposit(tx: TreasuryTx) -> bool:
    if tx._symbol == 'USDC' and tx.from_address.address in treasury.addresses and 'slip' in tx._events:
        for event in tx._events['slip']:
            if all(arg in event for arg in DEPOSIT_EVENT_ARGS) and Decimal(event['wad']) / 10**18 == tx.amount:
                return True

def is_usdc_cdp_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == 'USDC' and tx.to_address and tx.to_address.address in treasury.addresses and 'flux' in tx._events:
        for event in tx._events['flux']:
            if all(arg in event for arg in WITHDRAWAL_EVENT_ARGS) and Decimal(event['wad']) / 10**18 == tx.amount:
                return True

def is_dai(tx: TreasuryTx) -> bool:
    """ Returns True when minting or burning DAI. """
    if tx._symbol == "DAI":
        if tx.from_address.address == ZERO_ADDRESS:
            return True
        elif tx.to_address.address == "0xd42e1Cb8b98382df7Db43e0F09dFE57365659D16": # DSProxy
            return True

def is_dsr(tx: TreasuryTx) -> bool:
    """sending DAI to or receiving DAI back from Maker's DSR module"""
    return "Contract: DsrManager" in [tx._to_nickname, tx._from_nickname]
