
from brownie import chain
from y.networks import Network

from yearn.entities import TreasuryTx
from yearn.multicall2 import fetch_multicall
from yearn.treasury.accountant.constants import treasury, v1, v2
from yearn.utils import contract


def is_fees_v1(tx: TreasuryTx) -> bool:
    if chain.id != Network.Mainnet:
        return False

    if not tx.to_address or tx.to_address.address not in treasury.addresses:
        return False

    for vault in v1.vaults:
        if (
            tx.token.address.address != vault.token.address
            # Fees from single-sided strategies are not denominated in `vault.token`
            and not (tx._symbol == "y3Crv" and tx._from_nickname.startswith("Contract: Strategy") and tx._from_nickname.endswith("3pool"))
            and not (tx._symbol == "yyDAI+yUSDC+yUSDT+yTUSD" and tx._from_nickname.startswith("Contract: Strategy") and tx._from_nickname.endswith("ypool"))
            ):
            continue
        
        try:
            controller = contract(vault.vault.controller(block_identifier=tx.block))
        except Exception as e:
            known_exceptions = [
                "No data was returned - the call likely reverted",
            ]

            if str(e) not in known_exceptions:
                raise

            continue

        if [tx.from_address.address, tx.to_address.address] == fetch_multicall([controller, 'strategies',vault.token.address],[controller,'rewards'], block=tx.block):
            return True

    return False

def is_fees_v2(tx: TreasuryTx) -> bool:
    if any(
        tx.from_address.address == vault.vault.address 
        and tx.token.address.address == vault.vault.address
        and tx.to_address.address in treasury.addresses
        and tx.to_address.address == vault.vault.rewards(block_identifier=tx.block)
        for vault in v2.vaults + v2.experiments
    ):
        return True
    elif is_inverse_fees_from_stash_contract(tx):
        if tx.value_usd > 0:
            tx.value_usd *= -1
        return True
    return False

factory_strats = [
    ["Contract: StrategyCurveBoostedFactoryClonable", ["CRV", "LDO"]],
    ["Contract: StrategyConvexFactoryClonable", ["CRV", "CVX"]],
    ["Contract: StrategyConvexFraxFactoryClonable", ["CRV", "CVX", "FXS"]],
]

def is_factory_fees_v2(tx: TreasuryTx) -> bool:
    for strategy, tokens in factory_strats:
        if tx._from_nickname == strategy and tx._symbol in tokens:
            return True

def is_fees_v3(tx: TreasuryTx) -> bool:
    # Stay tuned...
    return False

def is_yearn_fed_fees(tx: TreasuryTx) -> bool:
    if tx.to_address and tx.to_address.address in treasury.addresses:
        # New version
        if tx._symbol in ["yvCurve-DOLA-U", "CRV"] and tx.from_address.address == "0x64e4fC597C70B26102464B7F70B1F00C77352910":
            return True
        # Old versions
        if tx._symbol in ["yvCurve-DOLA-U", "yveCRV-DAO"] and tx.from_address.address in ["0x09F61718474e2FFB884f438275C0405E3D3559d3", "0x7928becDda70755B9ABD5eE7c7D5E267F1412042"]:
            return True
        if tx._symbol == "INV" and tx._from_nickname == "Inverse Treasury" and tx._to_nickname == "ySwap Multisig":
            return True
        if tx.from_address.address == "0x9D5Df30F475CEA915b1ed4C0CCa59255C897b61B" and tx._to_nickname == "ySwap Multisig":
            return True
    return False

def is_dolafraxbp_fees(tx: TreasuryTx) -> bool:
    return tx._from_nickname == "Contract: StrategyConvexFraxBpRewardsClonable" and tx._to_nickname == "Yearn yChad Multisig" and tx._symbol == "yvCurve-DOLA-FRAXBP-U"

def is_temple(tx: TreasuryTx) -> bool:
    if tx._to_nickname in  ["Yearn Treasury", "Yearn yChad Multisig"]: # fees have been sent to both
        if tx._from_nickname == "Contract: StrategyConvexCrvCvxPairsClonable" and tx._symbol == "CRV":
            return True
        elif tx._from_nickname == "Contract: Splitter" and tx._symbol in ["yveCRV-DAO","CRV"]:
            return True

def is_inverse_fees_from_stash_contract(tx: TreasuryTx) -> bool:
    return tx.from_address.address == "0xE376e8e8E3B0793CD61C6F1283bA18548b726C2e" and tx.to_address.nickname == "Token: Curve stETH Pool yVault"
