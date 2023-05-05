
from brownie import chain
from y.networks import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher


def is_yacademy_audit(tx: TreasuryTx) -> bool:
    hashes = [
        "0x48e05bff53a67304593a0bff5238fd2bed01c61074937706df879fb901e9e1ba",
        "0xf3a31b7c162018f93c8485ad4e374a15e0053308148c7f9afe2f6d16b2013c19",
        ["0x3e75d22250d87c183824c3b77ddb9cb11935db2061ce7f34df4f024d0646fcfb", Filter('log_index', 116)],
        "0x7a7117d68adf198f295277ccabdecbca244eebe0d6c59200060f80a76406567e",
    ]
    return tx in HashMatcher(hashes)

def is_chainsec_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher({
        Network.Mainnet: [
            "0x7672b9d10b968c58525cff566a60bc8d44a6633f51a712e0eb00ecf88f86aef3",
            "0x4a77efb6234793b6316e11b6ef7f345f26d3d1b7b8edb8efffe1c0dc4cdfb0e0",
            ["0x44fdf3172c73b410400718badc7801a7fc496227b5325d90ed840033e16d8366", Filter('log_index', 390)],
            "0xfdca5bfef0061fa0cea28c04b08ac239f6cb3d708f23548cded80411575ae7ce",
            ["0xbe95bd4f46e2933953d726a231625852caf8e707bbc16fbda33d20e7ea1f3e6a", Filter('log_index', 310)],
            "0xea937a5c5298dd5b60c8e0f193798855b2641c64ced0f92b1d9fdef673ae508d",
        ],
    }.get(chain.id, []))

def is_decurity_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x3d1a0b2bb71f3b7118b1a4d5f9e78962809044616ae04659ef383141df678b4f"
    ])

def is_statemind_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xeb51cb5a3b4ae618be75bf3e23c2d8e333d93d5e81e869eca7f9612a30079822", Filter('log_index', 193)],
        ["0xcb79cbe5b68d04a1a3feab3360734277020ee0536380843a8c9db3e8356b81d6", Filter('log_index', 398)],
        ["0x3e75d22250d87c183824c3b77ddb9cb11935db2061ce7f34df4f024d0646fcfb", Filter('log_index', 115)]
    ])

def is_mixbytes_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xcb79cbe5b68d04a1a3feab3360734277020ee0536380843a8c9db3e8356b81d6", Filter('log_index', 399)],
    ])

def is_other_audit(tx: TreasuryTx) -> bool:
    hashes = [
        "0x7df5566cc9ff8ed0aafe126b74ad0e3957e62d530d007565ee32bd1303bcec32",
        "0x5e95d5b0773eefaef9c7187d5e9187a89717d269f48e5dcf707acfe1a7e55cb9",
        "0x9cfd1098c5459002a90ffa23931f7bbec430b3f2ec0ef2d3a641cef574eb0817",
        "0x70cdcffa444f70754a1df2d80a1adf9c432dfe678381e05ac78ab50b9de9d393",
        ["0x70ecc34da6c461a0bb9dadfbc4d082a8486e742cbb454f0f67b2df384fb9bffc", Filter("log_index", 89)]
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
