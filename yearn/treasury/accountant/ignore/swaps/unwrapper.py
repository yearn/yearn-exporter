
from yearn.entities import TreasuryTx


def is_unwrapper(tx: TreasuryTx) -> bool:
    return "Contract: Unwrapper" in [tx._from_nickname, tx._to_nickname]
