
from brownie import ZERO_ADDRESS
from y import Contract

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury


def is_reaper_withdrawal(tx: TreasuryTx) -> bool:
    
    # vault side
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == ZERO_ADDRESS and tx._symbol.startswith('rv'):
        events = tx._events
        if 'Transfer' not in events:
            return False

        # this code was commented out for some reason, I think its fine but leaving this msg jsut in case
        for event in events['Transfer']:
            sender, receiver, value = event.values()
            if event.address == tx.token.address.address and receiver == ZERO_ADDRESS:
                underlying = Contract(tx.token.address.address).token()
                for _event in events['Transfer']:
                    _sender, _receiver, _value = _event.values()
                    if _event.address == underlying and _receiver == tx.from_address.address and event.pos < _event.pos and _sender == tx.token.address.address:
                        return True
    # token side
    if tx.from_address.token and "Robovault" in tx.from_address.nickname:
        try:
            vault = Contract(tx.from_address.address)
        except ValueError as e:
            if "not verified" in str(e).lower():
                return False
            raise
        if vault.token() == tx.token.address.address:
            return True
    
    # DEV: why didn't these match?
    hashes = [
        ["0x84b64365e647e8c9c44b12819e8b7af02d5595933853c3da3eb43fc6f8ef3112",IterFilter('log_index',[8,12,16,74,78,82,86,73,7,11,77,81,15,85])],
        ["0xf68dee68d36eac87430f5238a520ae209650ddeea4b09ebe29af1b00623f1148",IterFilter('log_index',[19,27,7,26,11,23,15,22,14,2,6,10,18,3])]
    ]

    if HashMatcher(hashes).contains(tx):
        return True
