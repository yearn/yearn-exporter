from brownie import ZERO_ADDRESS

from yearn.entities import TreasuryTx


def is_atoken_yield(tx: TreasuryTx) -> bool:
    return (
        tx._symbol in ("aLEND", "aLINK")
        and tx.from_address.address == ZERO_ADDRESS
        and tx._to_nickname in ("Yearn Treasury", "Yearn Treasury V1")
    )
