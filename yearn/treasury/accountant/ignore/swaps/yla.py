
from yearn.entities import TreasuryTx


def is_yla_withdrawal(tx: TreasuryTx) -> bool:
    return bool(tx.to_address and "0x85c6D6b0cd1383Cc85e8e36C09D0815dAf36b9E9" in (tx.from_address.address, tx.to_address.address))