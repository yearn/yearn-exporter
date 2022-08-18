
from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import Filter, HashMatcher


def is_yacademy_audit(tx: TreasuryTx) -> bool:
    hashes = [
        "0x48e05bff53a67304593a0bff5238fd2bed01c61074937706df879fb901e9e1ba",
    ]
    return tx in HashMatcher(hashes)

def is_chaisec_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher({
        Network.Mainnet: [
        "0x7672b9d10b968c58525cff566a60bc8d44a6633f51a712e0eb00ecf88f86aef3",
        ],
    }.get(chain.id, []))

def is_statemind_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xeb51cb5a3b4ae618be75bf3e23c2d8e333d93d5e81e869eca7f9612a30079822", Filter('log_index', 193)]
    ])

def is_other_audit(tx: TreasuryTx) -> bool:
    hashes = [
        "0x7df5566cc9ff8ed0aafe126b74ad0e3957e62d530d007565ee32bd1303bcec32",
        "0x5e95d5b0773eefaef9c7187d5e9187a89717d269f48e5dcf707acfe1a7e55cb9",
        "0x9cfd1098c5459002a90ffa23931f7bbec430b3f2ec0ef2d3a641cef574eb0817",
        "0x70cdcffa444f70754a1df2d80a1adf9c432dfe678381e05ac78ab50b9de9d393",
    ]
    return tx in HashMatcher(hashes)

def is_bug_bounty(tx: TreasuryTx) -> bool:
    hashes = [
        "0x4df2eee567ebf2a41b555fca3fed41300b12ff2dc3c79ffaee8b7bdf262f9303",
    ]
    return tx in HashMatcher(hashes)

def is_antispam_bot(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xe397d5682ef780b5371f8c80670e0cd94b4f945c7b432319b24f65c288995a17", Filter('log_index',357)]
    ])
