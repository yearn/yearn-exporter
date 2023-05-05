
from yearn.entities import TreasuryTx

def is_rkp3r_redemption(tx: TreasuryTx) -> bool:
    return "Contract: SimpleRedeem" in [tx._from_nickname, tx._to_nickname]
