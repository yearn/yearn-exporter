

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher
from yearn.treasury.accountant.constants import treasury


def is_scdai_salvage(tx: TreasuryTx) -> bool:
    # scDAI sent to redeemer
    if tx.from_address.address in treasury.addresses and tx._to_nickname == "Contract: CRedeemer" and tx._symbol == "scDAI":
        return True
    # DAI salvaged
    if tx._from_nickname == "Contract: CRedeemer" and tx.to_address.address in treasury.addresses and tx._symbol == "DAI":
        return True
    # Leftover scDAI returned
    if tx._from_nickname == "Contract: CRedeemer" and tx.to_address.address in treasury.addresses and tx._symbol == "scDAI":
        return True
    
    return tx in HashMatcher([
        ["0x0697da950322dc5d9af2815e48752469208d59cbe4d3b93b1ef60202382ab843", Filter('log_index', 57)],
        ["0xf46aa51f26871c602bf527e8cfea706b6ca4cd0e0b816fb1cb3a134c4c3b931e", Filter('log_index', 5)],
    ])
