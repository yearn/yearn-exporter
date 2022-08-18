
from brownie import ZERO_ADDRESS, chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury


def is_pass_thru(tx: TreasuryTx) -> bool:
    pass_thru_hashes = {
        Network.Mainnet: [],
        Network.Fantom: [
            "0x411d0aff42c3862d06a0b04b5ffd91f4593a9a8b2685d554fe1fbe5dc7e4fc04",
            "0xa347da365286cc912e4590fc71e97a5bcba9e258c98a301f85918826538aa021",
        ],
    }.get(chain.id, [])
    # skipped the hashmatcher to do strange things... there is probably a better way to do this
    if tx.hash in pass_thru_hashes and str(tx.log_index).lower() != "nan":
        return True
    
    # Passing thru to yvWFTM
    if chain.id == Network.Fantom and tx._symbol == 'WFTM' and tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == "0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0":
        # dont want to accidenally sort a vault deposit here
        is_deposit = None
        for event in tx._events['Transfer']:
            sender, receiver, _ = event.values()
            if event.address == tx.to_address.address and sender == ZERO_ADDRESS and receiver == tx.from_address.address:
                is_deposit = True
        if not is_deposit:
            return True
    
    pass_thru_hashes = {
        Network.Fantom: [
            "0x14faeac8ee0734875611e68ce0614eaf39db94a5ffb5bc6f9739da6daf58282a",
        ],
    }.get(chain.id, [])

    if tx in HashMatcher(pass_thru_hashes):
        return True

def is_cvx(tx: TreasuryTx) -> bool:
    hashes = [
        ["0xf6f04b4832b70b09b089884a749115d4e77691b94625c38b227eb74ffc882121", IterFilter('_symbol', ['CVX','CRV'])],
        ["0xdc552229f5bd25c411b1bf51d19f5b40809094306b8790e34ba5ad3ef28be56c", IterFilter('_symbol', ['CVX','CRV'])],
    ]
    return tx in HashMatcher(hashes)

def is_ib(tx: TreasuryTx) -> bool:
    hashes = [
        ["0x71daf54660d038c5c4ed047c8e6c4bfda7e798fbb0628903e4810b39b57260b2", Filter('_symbol', 'IB')],
        ["0x7a21623b630e2429715cf3af0732bef79098f9354983c936a41a1831dab71306", Filter('_symbol', 'IB')],
        ["0x8fb5bb391c47a3c45b36562ffbce03d76edf11795477cae45e5a7393aac71bec", Filter('_symbol', 'IB')],
        ["0x773037a85ddafc5e30b62097932c3a35232e3d055cd1acdf5ef63dc2ce6f2c7c", Filter('_symbol', 'IB')],
    ]
    return tx in HashMatcher(hashes)

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
    
def is_buying_yvboost(tx: TreasuryTx) -> bool:
    """ Bought back yvBoost is unwrapped and sent back to holders. """
    yswap = '0x9008D19f58AAbD9eD0D60971565AA8510560ab41'
    if tx._symbol == 'SPELL' and tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == yswap:
        return True
    
    elif tx._symbol == "yveCRV-DAO" and tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address in ["0xd7240B32d24B814fE52946cD44d94a2e3532E63d","0x7fe508eE30316e3261079e2C81f4451E0445103b"]:
        return True
    
    elif tx._symbol == "3Crv" and tx.from_address.address == "0xd7240B32d24B814fE52946cD44d94a2e3532E63d" and tx.to_address and tx.to_address.address in treasury.addresses:
        return True
    
    hashes = [
        "0x9eabdf110efbfb44aab7a50eb4fe187f68deae7c8f28d78753c355029f2658d3",
        "0x5a80f5ff90fc6f4f4597290b2432adbb62ab4154ead68b515accdf19b01c1086",
        "0x848b4d629e137ad8d8eefe5db40eab895c9959b9c210d0ae0fef16a04bfaaee1",
        "0x896663aa9e2633b5d152028bdf84d7f4b1137dd27a8e61daca3863db16bebc4f",
        "0xd8aa1e5d093a89515530b7267a9fd216b97fddb6478b3027b2f5c1d53070cd5f",
        "0x169aab84b408fce76e0b776ebf412c796240300c5610f0263d5c09d0d3f1b062",
        "0xe6fefbf061f4489cd967cdff6aa8aca616f0c709e08c3696f12b0027e9e166c9",
    ]

    if tx in HashMatcher(hashes):
        return True

def is_yvboost_from_elsewhere(tx: TreasuryTx) -> bool:
    """ where is this from? who knows, doesn't matter yet. MUST INVESTIGATE """
    hashes = [
        "0x9366b851b5d84f898962fce62356f1d020f3220ec794476eb19cd8106ca08283",
    ]
    return tx in HashMatcher(hashes)

def is_inverse_fees_from_yearn_fed(tx: TreasuryTx) -> bool:
    if tx._symbol == "yvDOLA-U" and tx.from_address.address in treasury.addresses and tx.to_address and tx._to_nickname == "Contract: YearnFed":
        return True

def is_stkaave(tx: TreasuryTx) -> bool:
    """ stkAAVE is sent from a strategy to ychad, then to sms for unwrapping. """
    if tx._symbol == "stkAAVE":
        if tx._from_nickname and "Strategy" in tx._from_nickname and tx._to_nickname == "Yearn yChad Multisig":
            return True
        elif tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "Yearn Strategist Multisig":
            return True

def is_single_sided_ib(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0xcbc2edfd6f8eb2b89e474ae70efea06c2c24a3e0df3e69b5c598aee4626bca0f", IterFilter('log_index', [70, 71])],
        "0xc8bdb3c809219ad0f3285aa148e20bb29b604c0a1b6d30701a56cfdf930923b3"
    ])
