from decimal import Decimal

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_tessaract_refund(tx: TreasuryTx) -> bool:
    """
    Yearn sent Tessaract funds to help them get established on Polygon.
    It didn't work out, and the remaining funds were returned.
    """ 
    return tx in HashMatcher(("0xe1558686856dc43ca9797f9fd7113151e51fc69be35f36db3555b9cefd74399a",))

def is_lido_grant(tx: TreasuryTx) -> bool:
    return tx in HashMatcher((
        "0x2193a2e98487894a30fc1fc9b913ac7a59e14f47ab72b0b53a02aede7d919795",
        "0x64d9e139ac2b1738f4e3c1b1c2f979fc90544c9b9eed5cc8bcd960c73fc19ac8",
    ))

def is_portals_fees(tx: TreasuryTx) -> bool:
    return tx in HashMatcher((
        "0x7181e4956fde34580be7ebecc6b4b60ad06676b5bb88598a2d35706995bf1289",
        "0x3fd8a5995bfe7aa6bb4f502e4bd7e93f491c12f6a72f39644d2809a6eab8b57d",
    ))

def is_cowswap_gas_reimbursement(tx: TreasuryTx) -> bool:
    return tx._symbol == "ETH" and tx._from_nickname == "Cowswap Multisig" and tx._to_nickname == "yMechs Multisig"

def is_usdn_shutdown(tx: TreasuryTx) -> bool:
    """The USDN vault was shut down but the pool was so rekt they coulnd't even swap for want. Trace amounts of yield sent to yChad."""
    return tx in HashMatcher(("0x12b3687f4bfbc73c11dccbd61d18c3f785e6f0f91cb46280d7df08143162ceed",))

def is_usds_referral_code(tx: TreasuryTx) -> bool:
    """Yearn earns some USDS for referring deposits to Maker"""
    return tx._symbol == "USDS" and tx.from_address.address == "0x3C5142F28567E6a0F172fd0BaaF1f2847f49D02F"

is_other = HashMatcher(
    (
        "0x5be236c49e5c5481fc9169dbdd5759cb1542d5d8fe047083ecf2403584468e1a",
        "0x6fde3ebcdd3e4e176d3138a976a2382fe15e71922d0b9740f04d0a7be3d4d30f",
        "0xbd2a33818b9e755c78c159de5863e2a153164f526d12cfacc773139841d1e594",
    )
).contains
"""Some tokens showed up and nobody knew where they came from. Lucky Yearn."""

def is_yeth_application_fee(tx: TreasuryTx) -> bool:
    return tx._symbol == "yETH" and tx._to_nickname == "Yearn Treasury" and tx.amount == Decimal("0.1")

def is_yprisma_fees(tx: TreasuryTx) -> bool:
    return tx._symbol == "yvmkUSD-A" and tx._from_nickname == "Contract: YPrismaFeeDistributor"
