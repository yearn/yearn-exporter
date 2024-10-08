
from brownie import chain
from y.networks import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter


def is_yacademy_audit(tx: TreasuryTx) -> bool:
    hashes = [
        "0x48e05bff53a67304593a0bff5238fd2bed01c61074937706df879fb901e9e1ba",
        "0xf3a31b7c162018f93c8485ad4e374a15e0053308148c7f9afe2f6d16b2013c19",
        ["0x3e75d22250d87c183824c3b77ddb9cb11935db2061ce7f34df4f024d0646fcfb", Filter('log_index', 116)],
        "0x7a7117d68adf198f295277ccabdecbca244eebe0d6c59200060f80a76406567e",
        ["0x610941b6f2197408aabe5a8958ead79dfba44f7de39d2e9fd8a620420e0a0554", Filter('_symbol', 'USDT')],
    ]
    return tx in HashMatcher(hashes)

def is_chainsec_audit(tx: TreasuryTx) -> bool:
    if chain.id == Network.Mainnet and tx._symbol in ["USDC", "USDT"] and tx.to_address.address == "0x8bAf5eaF92E37CD9B1FcCD676918A9B3D4F87Dc7":
        return True
    return tx in HashMatcher(["0x83ec212072f82f4aba4b512051d52c5f016de79a620a580622a0f051e3473a78"])

def is_debaub_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0xb2595246e8387b80e35784aaade3a92bd3111bf9059c3b563516886d1aefcf3f",
    ])

def is_decurity_audit(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x3d1a0b2bb71f3b7118b1a4d5f9e78962809044616ae04659ef383141df678b4f",
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
        ["0xca61496c32806ba34f0deb331c32969eda11c947fdd6235173e6fa13d9a1c288", Filter('_symbol', 'USDC')],
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
        
        # Immunefi
        ["0x5deca5d6c934372c174bbef8be9a1e103e06d8b93fd3bf8d77865dfeb34fe3be", IterFilter('log_index', [100, 101])],
    ]
    return tx in HashMatcher(hashes)

def is_antispam_bot(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xe397d5682ef780b5371f8c80670e0cd94b4f945c7b432319b24f65c288995a17", Filter('log_index', 357)],
    ])

def is_warroom_help(tx: TreasuryTx) -> bool:
    """A past yearner was paid a one-time payment to assist in a war room."""
    return tx in HashMatcher([
        ["0xca61496c32806ba34f0deb331c32969eda11c947fdd6235173e6fa13d9a1c288", Filter('log_index', 152)]
    ])