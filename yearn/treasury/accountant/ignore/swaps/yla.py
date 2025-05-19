
from yearn.entities import TreasuryTx


def is_yla_deposit(tx: TreasuryTx) -> bool:
    return tx.hash == "0x1d4e974db2d60ebd994410fcd793c5db771af9a14660015faf94cbdaec285009" and (
        tx._symbol == "YLA" or tx.to_address and tx.to_address.address == "0x9ba60bA98413A60dB4C651D4afE5C937bbD8044B"
    )

def is_yla_withdrawal(tx: TreasuryTx) -> bool:
    return bool(tx.to_address and "0x85c6D6b0cd1383Cc85e8e36C09D0815dAf36b9E9" in (tx.from_address.address, tx.to_address.address))