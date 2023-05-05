
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_tessaract_refund(tx: TreasuryTx) -> bool:
    """
    Yearn sent Tessaract funds to help them get established on Polygon.
    It didn't work out, and the remaining funds were returned.
    """ 
    return tx in HashMatcher(["0xe1558686856dc43ca9797f9fd7113151e51fc69be35f36db3555b9cefd74399a"])

def is_cowswap_incentive(tx: TreasuryTx) -> bool:
    """ Incentives for swapping on CowSwap """
    return tx._symbol == "COW" and tx.from_address.address == "0xA03be496e67Ec29bC62F01a428683D7F9c204930"

def is_lido_grant(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(["0x2193a2e98487894a30fc1fc9b913ac7a59e14f47ab72b0b53a02aede7d919795"])

def is_portals_fees(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x7181e4956fde34580be7ebecc6b4b60ad06676b5bb88598a2d35706995bf1289",
        "0xFBD4C3D8bE6B15b7cf428Db2838bb44C0054fCd2",
    ])
