
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury


WITHDRAWAL_EVENT_ARGS = {"cdp", "dst", "wad"}

def is_yfi_cdp_deposit(tx: TreasuryTx) -> bool:
    pass

def is_yfi_cdp_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == 'YFI' and tx.to_address and tx.to_address.address in treasury.addresses and 'flux' in tx._events:
        for event in tx._events['flux']:
            if all(arg in event for arg in WITHDRAWAL_EVENT_ARGS) and round(event['wad'] / 1e18, 15) == round(float(tx.amount), 15):
                return True
