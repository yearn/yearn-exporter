
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher
from yearn.treasury.accountant.constants import treasury


def is_servers(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x08ef1aacdf7d0f16be5e6fd0a64ebd0ba3b0c3dd0a7884a9a470aa89a7fe1a06", Filter('log_index', 222)],
        ["0x0c59e87027bcdcaa718e322a28bc436106d73ae8623071930437bdb0706c4d65", Filter('token', "DAI")],
    ])

def is_tenderly(tx: TreasuryTx) -> bool:
    return tx._symbol == "USDT" and tx.from_address.address in treasury.addresses and tx.to_address in ["0xF6060cE3fC3df2640F72E42441355f50F195D96a"]

def is_wonderland(tx: TreasuryTx) -> bool:
    return tx._symbol == "DAI" and tx.from_address.address in treasury.addresses and tx.to_address == '0x8bA72884984f669aBBc9a5a7b441AD8E3D9a4fD3'

def is_generic(tx: TreasuryTx) -> bool:
    hashes = [
        ["0x47035f156d4e6144c144b2ac5e91497e353c9a4e23133587bbf3da2f9d7da596", Filter('_symbol', 'DAI')],
        ["0xeb51cb5a3b4ae618be75bf3e23c2d8e333d93d5e81e869eca7f9612a30079822", Filter('log_index', 195)],
        ["0x40352e7166bf5196aa1160302cfcc157facf99731af0e11741b8729dd84e131c", Filter('_symbol', 'DAI')],
        ["0x3e75d22250d87c183824c3b77ddb9cb11935db2061ce7f34df4f024d0646fcfb", Filter('log_index', 117)],
        ["0x1621ba5c9b57930c97cc43d5d6d401ee9c69fed435b0b458ee031544a10bfa75", Filter('log_index', 460)],
        "0xeac1e31beb90945f41c39a08763a0e3fbd4b18345ea71be8c8ff9a4b4fa358e6",
        "0x8fe97937c6a127086abc376a7d38aa97dad6b0fc16c324ebdd1cd2192f2191e6",
        "0x5cd6b1e13b021bd8fba4a1823c6ef8647d190f85083c15a1e6e3e5fd8a9df6ee",
        "0x020ee660197f91647d47fab8e279d0396c8d4781f5562c6d243e976d8102d2e4",
        "0xeb8d642da7b4f0981aca22b747489c67b09d86e75381da5d68d6c00448e440c8",
        ["0x5deca5d6c934372c174bbef8be9a1e103e06d8b93fd3bf8d77865dfeb34fe3be", Filter('log_index', 98)],
        "0x3160b025085b17ee4bc3810c753c2d1fe9c556d2fb4cdf2ec7669cc878a94c68",
        "0x17a72a66512aa302a4f89b7d894519abf335156deac2a4801c884283181daa83",
        "0xb9b5eef15987d97448d6cae146231c47910ba937db7dc30cfb253d64cbc5515d",
        ["0xfc07ee04d44f8e481f58339b7b8c998d454e4ec427b8021c4e453c8eeee6a9b9", Filter('log_index', 207)],
        "0xf9ddee2db73fdf322caa10da88a178aca8308d79c2ad83324716c22878600e1c",
        "0xaf303a94ca3949c44855dfe90848bef142f8afdaa7a524f51593c827c2d2d733",
        ["0xc269f6fb016a48fe150f689231a73532b631877d1376608df639dad79514904b", Filter('_symbol', 'DAI')],
    ]
    return tx in HashMatcher(hashes)
