
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury


def is_strategist_buyout(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x47035f156d4e6144c144b2ac5e91497e353c9a4e23133587bbf3da2f9d7da596", Filter("_symbol", "YFI")]
    ])

def is_gitcoin_matching_donation(tx: TreasuryTx) -> bool:
    gitcoin = "0xde21F729137C5Af1b01d73aF1dC21eFfa2B8a0d6"
    return tx.from_address.address in treasury.addresses and tx.to_address == gitcoin and tx._symbol in ["DAI", "USDC"]

def is_yacademy_fellow_grant(tx: TreasuryTx) -> bool:
    return tx._from_nickname == "Disperse.app" and tx in HashMatcher([
        "0x2b74fb1a5deadbb0885dfa33502304382525a0847350a688b707b3882930eeab",
        "0x028eff213177fbfa170bc9a3227096b1d688a8b6191c8ec06321299a5396949f",
    ])

def is_yfi_story(tx: TreasuryTx) -> bool:
    story_dot_ychad_dot_eth = "0x93C6c14C134C4fF52cbB6BC2f50F19d84874cDD1"
    return tx.to_address == story_dot_ychad_dot_eth
    
def is_aztek_gas_subsidy(tx: TreasuryTx) -> bool:
    return tx.to_address == "0xABc30E831B5Cc173A9Ed5941714A7845c909e7fA"

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
        "0x706f5891441d58820be67c99d31e4fe24b20f9e5fd751a0567520bfd2a7008ca",
    ])

def is_vesting_packages(tx: TreasuryTx) -> bool:
    return tx._symbol == "YFI" and tx in HashMatcher([
        "0x6532f364035f392cf353e1b3f77b4be6e7f2b56c1ad541d1bb8c45cb61462c3f",
        "0x9b8f9dfaaedceaeb2b286db92f2aba2d2e519954b47a2d603cd4ce5fd03336fe",
        "0xe4b770cdbc0fce9d9acec45beb02113b50cb6903c2868b89c46f5d9382a6071f",
        "0x706f5891441d58820be67c99d31e4fe24b20f9e5fd751a0567520bfd2a7008ca",
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

def is_4626_alliance(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xca61496c32806ba34f0deb331c32969eda11c947fdd6235173e6fa13d9a1c288", Filter('log_index', 150)],
    ])

def is_yeth_bootstrap(tx: TreasuryTx) -> bool:
    return tx.token == "ETH" and tx.hash == '0x0c59e87027bcdcaa718e322a28bc436106d73ae8623071930437bdb0706c4d65' and tx._from_nickname == "Yearn yChad Multisig"

def is_warroom_games(tx: TreasuryTx) -> bool:
    return tx.hash == "0x8f17ead9cea87166cf99ed2cdbc46dfdf98c04c261de5b5167caddce5f704cb2" and tx.log_index in [429,430,431]

def is_yfi_dot_eth(tx: TreasuryTx) -> bool:
    return tx.hash == "0x7c9e50cab268ae67d563ec3e563ebbf6a38a66dfdb02c65d22320d7239480a99"

def is_yyper_contest(tx: TreasuryTx) -> bool:
    """Grant for a vyper compiler audit context, vyper-context.eth"""
    return tx in HashMatcher([["0xb8bb3728fdfb49d7c86c08dba8e3586e3761f13d2c88fa6fab80227b6a3f4519", Filter('log_index', 202)]])

def is_reimburse_yeth_applications(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([["0x846d475425a1a70469b8674b6f15568c83a14ed3251cafa006811722af676f44", Filter('_symbol', 'ETH')]])

def is_dyfi_launch(tx: TreasuryTx) -> bool:
    if tx in HashMatcher(["0x2ec726e5ee52cdc063e61795d1b96a75d16fd91824136c990b7c3ddd52b28e31"]):
        # unused returned
        if tx.amount > 0:
            tx.amount *= -1
        if tx.value_usd > 0:
            tx.value_usd *= -1
        return True
    return tx in HashMatcher([
        "0x066c32f02fc0908d55b6651afcfb20473ec3d99363de222f2e8f4a7e0c66462e",
    ])

def is_dyfi_redemptions(tx: TreasuryTx) -> bool:
    """YFI going to the dyfi redemptions contract"""
    return tx._symbol == "YFI" and tx._to_nickname == "dYFI Redemption Contract"

def is_veyfi_launch(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([["0x51202f9e8a9afa84a9a0c37831ca9a18508810175cb95ab7c52691bbe69a56d5", Filter('_symbol', 'YFI')]])

def is_unknown(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xdf3e6cf2e50052e4eeb57fb2562b5e1b02701014ce65b60e6c8a850c409b341a", IterFilter('log_index', [121, 122])],
        "0x81fd665147690345100c385d273135dba3b4163b17ccc7d7c7b48fb636297205",
    ])

def is_vyper_donation(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x70CCBE10F980d80b7eBaab7D2E3A73e87D67B775"

def is_ybudget_reward(tx: TreasuryTx) -> bool:
    return tx.hash == "0xa1b242b2626def6cdbe49d92a06aad96fa018c27b48719a98530c5e5e0ac61c5"