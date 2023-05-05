
from decimal import Decimal

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
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
        "0x028eff213177fbfa170bc9a3227096b1d688a8b6191c8ec06321299a5396949f",
    ]
    if tx._from_nickname == "Disperse.app":
        return tx in HashMatcher(hashes)

def is_yfi_story(tx: TreasuryTx) -> bool:
    story_dot_ychad_dot_eth = "0x93C6c14C134C4fF52cbB6BC2f50F19d84874cDD1"
    if tx.to_address and tx.to_address.address == story_dot_ychad_dot_eth:
        return True
    
def is_aztek_gas_subsidy(tx: TreasuryTx) -> bool:
    return tx.to_address and tx.to_address.address == "0xABc30E831B5Cc173A9Ed5941714A7845c909e7fA"

def is_devcon_event(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ['0x57bc99f6007989606bdd9d1adf91c99d198de51f61d29689ee13ccf440b244df', Filter('log_index', 83)],
    ])

def is_eth_global(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x5b2e904506a54417c054129a01b84c43dd40050d6f8064463e2500195049a070",
        "0xd667fda716cf9b5e3a8ca6c9729914505ed611eff37b0f5f57d365b302ce6ebc",
    ])

def is_veyfi_gas(tx: TreasuryTx) -> bool:
    """ a gas subsidy for contributors to fund their veyfi wallet """

    return tx._symbol == "ETH" and tx in HashMatcher([
        "0x8ed7ee716e04096a7274188b5b371bc7c92aff305fa7b47f32ad622374fb23fc",
        "0x9b8f9dfaaedceaeb2b286db92f2aba2d2e519954b47a2d603cd4ce5fd03336fe",
        "0xe4b770cdbc0fce9d9acec45beb02113b50cb6903c2868b89c46f5d9382a6071f",
    ])

def is_vesting_packages(tx: TreasuryTx) -> bool:
    return tx._symbol == "YFI" and tx in HashMatcher([
        "0x6532f364035f392cf353e1b3f77b4be6e7f2b56c1ad541d1bb8c45cb61462c3f",
        "0x9b8f9dfaaedceaeb2b286db92f2aba2d2e519954b47a2d603cd4ce5fd03336fe",
        "0xe4b770cdbc0fce9d9acec45beb02113b50cb6903c2868b89c46f5d9382a6071f",
    ])

def is_strategist_buyout(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x8ed7ee716e04096a7274188b5b371bc7c92aff305fa7b47f32ad622374fb23fc",
    ])

def one_yfi_for_signers(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(["0x86700207761cdca82a0ad4e04b49b749913de63c8bd933b4f3f9a145d9b2c1fa"])

def send_one_yfi_get_two_back(tx: TreasuryTx) -> bool:
    """ yearn asked for donations once and instead of using them, repaid them x2 """ 
    return tx in HashMatcher(["0xf7ec6d776412e4bd96bfe33fc57d2669f79c917f3f1c7f3a48253dc426f57f59"])

def is_new_stream_gas_subsidy(tx: TreasuryTx) -> bool:
    """ Sometimes a new stream is created and the recipient will need a small amount of ETH for their first transaction. """ 
    return tx in HashMatcher([
        ["0x6e0ac8f06aaf977a844b5935c34c558c8d0e596515e03ae43ea756e08d732a76", Filter('_symbol', 'ETH')]
    ])

def is_fix_temple_migration(tx: TreasuryTx) -> bool:
    """Temple migration transaction did not honor proper split ratios. Sent the full amount manually using proper split ratio."""
    return tx in HashMatcher([
        ["0xfdb9e1e3bfe7aead37c5c2ff4952434be6db9f37980677410e9a40eb05a1730b", Filter('log_index', 240)],
    ])

def is_ychute(tx: TreasuryTx) -> bool:
    """Parachute incentive"""
    return tx in HashMatcher([
        ["0x8a9a652090ab73e981c4f4563421e0c2fd589f4eb75f21d6101391f96cbfc33e", Filter('_symbol', 'DAI')],
        ["0x6f8134bcb16e47fdcc51a23afabd83046b10dc3c3b7267612a3bbed77c7e3c24", IterFilter('log_index', [167, 168])],
        ["0x9e113dda11fcd758df2fe94a641aa7afe6329afec4097a8cb5d6fb68489cf7d8", Filter('log_index', 97)],
    ])
    
def is_eth_online_prizes(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(["0x200cbcd15fb934e75e0909e4752cad4e2067b9556a85660bd6980c3473721122"])
