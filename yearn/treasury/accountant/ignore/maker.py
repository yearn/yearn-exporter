from decimal import Decimal

from brownie import ZERO_ADDRESS

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury


def is_yfi_cdp_deposit(tx: TreasuryTx) -> bool:
    if tx._symbol == 'YFI' and tx.from_address.address in treasury.addresses and slip_in_events(tx):
        for event in tx._events['slip']:
            if all(arg in event for arg in ("ilk", "usr", "wad")) and Decimal(event['wad']) / 10**18 == tx.amount:
                return True
    return False

def is_yfi_cdp_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == 'YFI' and tx.to_address.address in treasury.addresses and flux_in_events(tx):
        for event in tx._events['flux']:
            if all(arg in event for arg in ("cdp", "dst", "wad")) and Decimal(event['wad']) / 10**18 == tx.amount:
                return True
    return False

def is_usdc_cdp_deposit(tx: TreasuryTx) -> bool:
    if tx._symbol == 'USDC' and tx.from_address.address in treasury.addresses and slip_in_events(tx):
        for event in tx._events['slip']:
            if all(arg in event for arg in DEPOSIT_EVENT_ARGS) and Decimal(event['wad']) / 10**18 == tx.amount:
                return True
    return False

def is_usdc_cdp_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == 'USDC' and tx.to_address.address in treasury.addresses and flux_in_events(tx):
        for event in tx._events['flux']:
            if all(arg in event for arg in WITHDRAWAL_EVENT_ARGS) and Decimal(event['wad']) / 10**18 == tx.amount:
                return True
    return False

def flux_in_events(tx: TreasuryTx) -> bool:
    try:
        return 'flux' in tx._events
    except KeyError as e:
        # This happens sometimes due to a busted abi and shouldnt impact us
        if str(e) == "'components'":
            return False
        raise

def slip_in_events(tx: TreasuryTx) -> bool:
    try:
        return 'slip' in tx._events
    except KeyError as e:
        # This happens sometimes due to a busted abi and shouldnt impact us
        if str(e) == "'components'":
            return False
        raise

DSPROXY = "0xd42e1Cb8b98382df7Db43e0F09dFE57365659D16"

def is_dai(tx: TreasuryTx) -> bool:
    """ Returns True when minting or burning DAI. """
    return tx._symbol == "DAI" and (tx.from_address == ZERO_ADDRESS or tx.to_address == DSPROXY)

def is_dsr(tx: TreasuryTx) -> bool:
    """sending DAI to or receiving DAI back from Maker's DSR module"""
    return "Contract: DsrManager" in [tx._to_nickname, tx._from_nickname]
