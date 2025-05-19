from brownie import ZERO_ADDRESS

from yearn.entities import TreasuryTx


def is_pooltogether_deposit(tx: TreasuryTx) -> bool:
    return (
        (tx._symbol == "POOL" and tx.to_address.address == "0x396b4489da692788e327E2e4b2B0459A5Ef26791")
        or (tx._symbol == "PPOOL" and tx.from_address.address == ZERO_ADDRESS)
    )
