
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_tessaract_refund(tx: TreasuryTx) -> bool:
    """
    Yearn sent Tessaract funds to help them get established on Polygon.
    It didn't work out, and the remaining funds were returned.
    """ 
    return tx in HashMatcher(["0xe1558686856dc43ca9797f9fd7113151e51fc69be35f36db3555b9cefd74399a"])
