
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher
from yearn.treasury.accountant.constants import treasury


def is_strategist_buyout(tx: TreasuryTx) -> bool:
    hashes = [
        ["0x47035f156d4e6144c144b2ac5e91497e353c9a4e23133587bbf3da2f9d7da596", Filter("_symbol", "YFI")]
    ]
    return tx in HashMatcher(hashes)

def is_gitcoin_matching_donation(tx: TreasuryTx) -> bool:
    gitcoin = "0xde21F729137C5Af1b01d73aF1dC21eFfa2B8a0d6"
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == gitcoin and tx._symbol in ["DAI", "USDC"]:
        return True

def is_yacademy_fellow_grant(tx: TreasuryTx) -> bool:
    hashes = [
        "0x2b74fb1a5deadbb0885dfa33502304382525a0847350a688b707b3882930eeab",
    ]
    if tx._from_nickname == "Disperse.app":
        return tx in HashMatcher(hashes)

def is_yfi_story(tx: TreasuryTx) -> bool:
    story_dot_ychad_dot_eth = "0x93C6c14C134C4fF52cbB6BC2f50F19d84874cDD1"
    if tx.to_address and tx.to_address.address == story_dot_ychad_dot_eth:
        return True
    