
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher


def is_double_fee_reimbursement(tx: TreasuryTx) -> bool:
    """
    Due to new single-sided strats that deposit into other vaults,
    some users were accidentally charged 2x the expected withdrawal fee.
    """
    hashes = [
        "0x4ce0c829fb46fc1ea03e434599a68af4c6f65f80aff7e934a008c0fe63e9da3f",
        "0x90b54bf0d35621160b5094c263a2684f8e7b37fc6467c8c1ce6a53e2e7acbfa1",
    ]
    if tx._from_nickname == "Disperse.app" and tx in HashMatcher(hashes):
        return True
    return False

def is_ydai_fee_reimbursement(tx: TreasuryTx) -> bool:
    if tx._from_nickname == "Disperse.app" and tx in HashMatcher(["0x2f667223aaefc4b153c28440d151fdb19333aff5d052c0524f2804fbd5a7964c"]):
        return True
    return False

def is_yyfi_fee_reimbursement(tx: TreasuryTx) -> bool:
    if tx._from_nickname == "Disperse.app" and tx in HashMatcher(["0x867b547b67910a08c939978d8071acca28ecc444d7155c0626e87730f67c058c"]):
        return True
    return False

def is_lossy_fee_reimbursement(tx: TreasuryTx) -> bool:
    """old vault code doesn't prevent fees from making harvest lossy. so here we airdrop the fee-take back to vault and do some housekeeper to prevent this from happening on other strats."""
    return tx in HashMatcher([["0x61eea3d40b2dc8586a5d20109ed962998c43cc55a37c300f283820150490eaa0", Filter('log_index', 179)]])

def is_stycrv(tx: TreasuryTx) -> bool:
    """Some user lost some funds in a minor issue, then was reimbursed."""
    return tx in HashMatcher([["0x491f07d134f3253ef06a2b46d83b82cdf2927b13cce4d38225d92ce01799da96", Filter('log_index', 197)]])

def is_slippage_bug_reimbursement(tx: TreasuryTx) -> bool:
    """a swap tx was messed up so Yearn sent treasury funds to the relevant strategy to compensate"""
    return tx in HashMatcher([
        "0xffe3883e34ae0b6ae3a7f304f00c625a7b315a021cf38f47a932e81d3f1c371c",
        "0x42cfcaa06beebe61547724f22fa790c763b2937ca2af8e3d5dbc680b903aad69",
        
        # separate slippage event
        ["0xc179e27f0e38bca52744d71dc6ff2463ed10fa918908ce28adcf4f4c0d6d6a1e", Filter('log_index', 103)],
        ["0x51c611597574aaa3b829004363476b1c2a4dc2941dff695c26c100498b695b4f", Filter('log_index', 214)],
    ])

def is_opti_zap_bug(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(["0xf1bc9683863fd7133377e618e80a7035bc9389e7abf3f650aed4df8b068a2b79"])
