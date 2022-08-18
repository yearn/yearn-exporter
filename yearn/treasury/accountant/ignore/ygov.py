from yearn.entities import TreasuryTx
from yearn.special import Ygov

def is_sent_to_ygov(tx: TreasuryTx) -> bool:
    if tx._from_nickname == "Yearn Treasury" and tx._symbol == "yDAI+yUSDC+yUSDT+yTUSD" and tx.to_address.address == Ygov().vault.address:
        return True
