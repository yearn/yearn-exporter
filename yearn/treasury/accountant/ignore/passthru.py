
from decimal import Decimal

from brownie import ZERO_ADDRESS, chain
from y import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury


_pass_thru_hashes = {
    Network.Mainnet: [
        "0xf662c68817c56a64b801181a3175c8a7e7a5add45f8242990c695d418651e50d",
    ],
    Network.Fantom: [
        "0x411d0aff42c3862d06a0b04b5ffd91f4593a9a8b2685d554fe1fbe5dc7e4fc04",
        "0xa347da365286cc912e4590fc71e97a5bcba9e258c98a301f85918826538aa021",
    ],
}.get(chain.id, [])

def is_pass_thru(tx: TreasuryTx) -> bool:
    # skipped the hashmatcher to do strange things... there is probably a better way to do this
    if tx.hash in _pass_thru_hashes and str(tx.log_index).lower() != "nan":
        return True
    
    # Passing thru to yvWFTM
    if chain.id == Network.Fantom and tx._symbol == 'WFTM' and tx.from_address.address in treasury.addresses and tx.to_address == "0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0":
        # dont want to accidenally sort a vault deposit here
        is_deposit = None
        for event in tx._events['Transfer']:
            sender, receiver, _ = event.values()
            if tx.to_address == event.address and sender == ZERO_ADDRESS and tx.from_address == receiver:
                is_deposit = True
        if not is_deposit:
            return True

    return tx in HashMatcher({
        Network.Mainnet: [
            ["0x51baf41f9daa68ac7be8024125852f1e21a3bb954ea32e686ac25a72903a1c8e", IterFilter('_symbol',['CRV','CVX'])],
            ["0xdc4e0045901cfd5ef4c6327b846a8bd229abdbf289547cd0e969874b47124342", IterFilter('log_index',[28,29,30,31])],
            "0xae6797ad466de75731117df46ccea5c263265dd6258d596b9d6d8cf3a7b1e3c2",
            "0x2a6191ba8426d3ae77e2a6c91de10a6e76d1abdb2d0f831c6c5aad52be3d6246",
            "0x25b54e113e58a3a4bbffc011cdfcb8c07a0424f33b0dbda921803d82b88f1429",  # https://github.com/yearn/chief-multisig-officer/pull/924
            "0xcb000dd2b623f9924fe0234831800950a3269b2d412ce9eeabb0ec65cd737059",
            ["0xd782e3923961ea7462584d61e0e37cf10289158a8cc338adb77b3ad38c72c459", Filter("_symbol", "COW")],
        ],
        Network.Fantom: [
            "0x14faeac8ee0734875611e68ce0614eaf39db94a5ffb5bc6f9739da6daf58282a",
        ],
    }.get(chain.id, []))

_cvx_hashes = [
    ["0xf6f04b4832b70b09b089884a749115d4e77691b94625c38b227eb74ffc882121", IterFilter('_symbol', ['CVX','CRV'])],
    ["0xdc552229f5bd25c411b1bf51d19f5b40809094306b8790e34ba5ad3ef28be56c", IterFilter('_symbol', ['CVX','CRV'])],
]

def is_cvx(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(_cvx_hashes)

_ib_hashes = [
    ["0x71daf54660d038c5c4ed047c8e6c4bfda7e798fbb0628903e4810b39b57260b2", Filter('_symbol', 'IB')],
    ["0x7a21623b630e2429715cf3af0732bef79098f9354983c936a41a1831dab71306", Filter('_symbol', 'IB')],
    ["0x8fb5bb391c47a3c45b36562ffbce03d76edf11795477cae45e5a7393aac71bec", Filter('_symbol', 'IB')],
    ["0x773037a85ddafc5e30b62097932c3a35232e3d055cd1acdf5ef63dc2ce6f2c7c", Filter('_symbol', 'IB')],
]

def is_ib(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(_ib_hashes)

def is_curve_bribe(tx: TreasuryTx) -> bool:
    """ All present and future curve bribes are committed to yveCRV holders. """
    if (
        tx._from_nickname == "Contract: CurveYCRVVoter"
        and tx.hash not in [
            # took place before bribes were committed to yveCRV
            "0x6824345c8a0c1f0b801d8050bb6f587032c4a9fa153faa113d723a2068d844f4",
            # was a whitehat hack of the v1 bribe contract, necessary to safeguard user funds
            "0xfcef3911809770fe351b2b526e4ee0274589a3f7d6ef9408a8f5643fa006b771",
        ]
    ):
        return True
        
    # Bribe V3
    elif tx._from_nickname == "Contract: yBribe" and tx._to_nickname in ["Yearn Treasury","ySwap Multisig"]:
        return True
    
    # NOTE: I added this to capture tokens sent to 
    return tx in HashMatcher([
        "0xce45da7e3a7616ed0c0d356d6dfa8a784606c9a8034bae9faa40abf7b52be114",
    ])
    
_yvboost_hashes = [
    "0x9eabdf110efbfb44aab7a50eb4fe187f68deae7c8f28d78753c355029f2658d3",
    "0x5a80f5ff90fc6f4f4597290b2432adbb62ab4154ead68b515accdf19b01c1086",
    "0x848b4d629e137ad8d8eefe5db40eab895c9959b9c210d0ae0fef16a04bfaaee1",
    "0x896663aa9e2633b5d152028bdf84d7f4b1137dd27a8e61daca3863db16bebc4f",
    "0xd8aa1e5d093a89515530b7267a9fd216b97fddb6478b3027b2f5c1d53070cd5f",
    "0x169aab84b408fce76e0b776ebf412c796240300c5610f0263d5c09d0d3f1b062",
    "0xe6fefbf061f4489cd967cdff6aa8aca616f0c709e08c3696f12b0027e9e166c9",
    "0x10be8a3345660f3c51b695e8716f758b1a91628bd612093784f0516a604f79c1",
]

def is_buying_yvboost(tx: TreasuryTx) -> bool:
    """ Bought back yvBoost is unwrapped and sent back to holders. """
    yswap = '0x9008D19f58AAbD9eD0D60971565AA8510560ab41'
    if tx._symbol == 'SPELL' and tx.from_address.address in treasury.addresses and tx.to_address == yswap:
        return True
    
    elif tx._symbol == "yveCRV-DAO" and tx.from_address.address in treasury.addresses and tx.to_address in ["0xd7240B32d24B814fE52946cD44d94a2e3532E63d","0x7fe508eE30316e3261079e2C81f4451E0445103b"]:
        return True
    
    elif tx._symbol == "3Crv" and tx.from_address == "0xd7240B32d24B814fE52946cD44d94a2e3532E63d" and tx.to_address.address in treasury.addresses:
        return True
    
    # SPELL bribe handling
    elif tx._symbol == "SPELL":
        if tx._to_nickname in ["Abracadabra Treasury", "Contract: BribeSplitter"]:
            return True
        
    return tx in HashMatcher(_yvboost_hashes)

_more_yvboost_hashes = [
    "0x9366b851b5d84f898962fce62356f1d020f3220ec794476eb19cd8106ca08283",
    ["0x47bcb48367b5c724780b40a19eed7ba4f623de619e98c30807f52be934d28faf", Filter('log_index', 285)],
    "0x17e2744e2959ba380f45383bcce11ec18e0a6bdd959d09cacdc7bb34008b14aa",
    ["0x40352e7166bf5196aa1160302cfcc157facf99731af0e11741b8729dd84e131c", Filter('log_index', 125)],
    "0xa025624820105a9f6914a13d5b50bd42e599b2093c8edb105321a43a86cfeb38",
]

def is_yvboost_from_elsewhere(tx: TreasuryTx) -> bool:
    """ where is this from? who knows, doesn't matter yet. MUST INVESTIGATE """
    return tx in HashMatcher(_more_yvboost_hashes)

def is_inverse_fees_from_yearn_fed(tx: TreasuryTx) -> bool:
    return tx._symbol == "yvDOLA-U" and tx.from_address.address in treasury.addresses and tx._to_nickname == "Contract: YearnFed"

def is_stkaave(tx: TreasuryTx) -> bool:
    """ stkAAVE is sent from a strategy to ychad, then to sms for unwrapping. """
    if tx._symbol == "stkAAVE":
        if tx._from_nickname and "Strategy" in tx._from_nickname and tx._to_nickname == "Yearn yChad Multisig":
            return True
        elif tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "Yearn Strategist Multisig":
            return True
    return False

def is_single_sided_ib(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xcbc2edfd6f8eb2b89e474ae70efea06c2c24a3e0df3e69b5c598aee4626bca0f", IterFilter('log_index', [70, 71])],
        "0xc8bdb3c809219ad0f3285aa148e20bb29b604c0a1b6d30701a56cfdf930923b3"
    ])

def is_cowswap_migration(tx: TreasuryTx) -> bool:
    """ A one-time tx that transferred tokens from an old contract to its replacement. """
    return tx in HashMatcher({
        Network.Mainnet: [
            "0xb50341d3db2ff4a39b9bfa21753893035554ae44abb7d104ab650753db1c4855",
        ],
    }.get(chain.id, []))

def is_usdc_stabeet(tx: TreasuryTx) -> bool:
    """ USDC is sent from a strategy to fchad for unwrapping, then back to the strategy. """
    return tx in HashMatcher(["0x97fa790c34e1da6c51ebf7b0c80e08e6b231e739c949dddca3054708e43bb5d0"])

def is_rkp3r(tx: TreasuryTx) -> bool:
    if tx._symbol == "rKP3R":
        if tx._from_nickname == "Contract: StrategyConvexFixedForexClonable" and tx._to_nickname == "Yearn yChad Multisig":
            return True
        elif tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "Contract: StrategyConvexFixedForexClonable":
            return True
    return False

def is_stg(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x06f8ab43d82468d4a8d0b6000315e2460ddeeab85d6d21a8b801e8618e1626f8",
        "0x11ade74701b65b93ec728dccde09ca01a2c0a9a6a64fdfab5bb2a89f77fbce88",
        "0xfb47e5006d78fd84d0af97f7a845fafe264373058bc7d6b530b1f5303a835bbe",
        "0xbcc751d5ec29d901199b93a4618aed631e42be02a0f73cdf699844ec7e707c63",
        ["0x1621ba5c9b57930c97cc43d5d6d401ee9c69fed435b0b458ee031544a10bfa75", Filter("_symbol", "STG")],
        "0x192f445df3058c214802ab79ea6d20b8549212fe60f27025ea139d780b04c900",
    ])

def is_idle(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        "0x59595773ee4304ba4e7e06d2c02541781d93867f74c6c83056e7295b684036c7",
        "0x4c7685aa3dfa9f375c612a2773951b9edbe059102b505423ed28a97d2692e75a",
        "0xb17317686b57229aeb7f06103097b47dc2eafa34489c40af70d2ac57bcf8f455",
        "0xfd9e6fd303fdbb358207bf3ba069b7f6a21f82f6b082605056d54948127e81e8",
        "0x41c8428fd361c54bb80cdac752e31622915ac626dd1e9270f02af1dc2c84d1f9",
    ])

def is_convex_strat(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x1621ba5c9b57930c97cc43d5d6d401ee9c69fed435b0b458ee031544a10bfa75", IterFilter("_symbol", ["CRV", "CVX"])],
    ])

def is_aura(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x1621ba5c9b57930c97cc43d5d6d401ee9c69fed435b0b458ee031544a10bfa75", IterFilter("_symbol", ["BAL", "AURA"])],
        ["0x996b5911a48319133f50f72904e70ed905c08c81e2c03770e0ccc896be873bd4", Filter("_symbol", "AURA")],
    ])

cowswap_router = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
ycrv = "0xFCc5c47bE19d06BF83eB04298b026F81069ff65b"

def is_ycrv(tx: TreasuryTx) -> bool:
    """ These are routed thru cowswap with dai as the purchase token. """ 
    yswaps = "0x7d2aB9CA511EBD6F03971Fb417d3492aA82513f0"
    ymechs = "0x2C01B4AD51a67E2d8F02208F54dF9aC4c0B778B6"
    if (tx.from_address == yswaps and tx._symbol == "DAI") or (tx.from_address == ymechs and tx._symbol == "3Crv"):
        if tx.to_address == cowswap_router:
            if "Trade" in tx._events:
                for trade in tx._events["Trade"]:
                    owner, sell_token, buy_token, sell_amount, buy_amount, fee_amount, order_uid = trade.values()
                    if tx.from_address == owner and tx.token == sell_token and buy_token == ycrv and Decimal(sell_amount) / 10 ** 18 == tx.amount:
                        return True
                    print(f"Trade: {trade}")
            else:
                print(f"no Trade event in {tx.hash}")
    
    elif tx in HashMatcher([
        # one off exception case to correct accounting mix-up
        "0x1578f3b0d3158d305167c39dc29ada08914e1ddb67ef9698e1b0421432f9aed6",
        # A few donations from ySwap
        "0xb2e335500b33b42edd8a97f57db35e0561df9a3a811d0cd73dce9767c23da0c4",
        "0xc02aab3a84b3bbfbc18f0ee6aa742f233d97511f653b4a40e7cd8f822851e10a",
        "0x8a2dba62eac44fdfc7ff189016ac601c9da664f5dea42d647f2e552319db2f7d",
        "0xd2c0a137d03811c5e4c27be19c7893f7fdd5851bdd6f825ee7301f3634033035",
    ]):
        return True
    return is_dola_bribe(tx)
        
def is_sent_to_dinoswap(tx: TreasuryTx) -> bool:
    """ These tokens are dumpped and the proceeds sent back to the origin strategy. """
    return chain.id == Network.Mainnet and tx._from_nickname == "Contract: Strategy" and tx._to_nickname == "yMechs Multisig"

def is_dola_bribe(tx: TreasuryTx) -> bool:
    return tx._from_nickname == "ySwap Multisig" and tx._to_nickname == "Contract: GPv2Settlement" and tx._symbol == "DOLA"

def is_bal(tx: TreasuryTx) -> bool:
    return tx._symbol == "BAL" and tx in HashMatcher([
        "0xf4677cce1a08ecd54272cdc1b23bc64693450f8bb5d6de59b8e58e288ec3b2a7",
    ])

def is_yprisma_migration(tx: TreasuryTx) -> bool:
    return tx in HashMatcher(["0xed39b66c01e25b053117778c80e544c985d962522233b49ce6f7fe136b1a4474"])

_factory_strat_to_yield_tokens = {
    "Contract: StrategyCurveBoostedFactoryClonable": ["CRV", "LDO"],
    "Contract: StrategyConvexFactoryClonable": ["CRV", "CVX"],
    "Contract: StrategyConvexFraxFactoryClonable": ["CRV", "CVX", "FXS"],
}

def is_factory_vault_yield(tx: TreasuryTx) -> bool:
    if tx._to_nickname == "yMechs Multisig" and tx._symbol in _factory_strat_to_yield_tokens.get(tx._from_nickname, []):
        return True
    return tx in HashMatcher({
        # TODO: figure out why these didn't match and update the sort rule
        Network.Mainnet: [
            "0xefea7be3abc943d0aa0eedfbc9e3db4677e1bd92511265ad0cb619bea1763d14",
            "0x2f9fefebde546c00a5c519e370e1205058aad8a3881d0bbd2b3d433ed9da6cb3",
            "0x3d0624e984904f9a77ad83453ab01841e870804bfd96fadaced62fcad6fc1507",
        ],
    }.get(chain.id, []))
