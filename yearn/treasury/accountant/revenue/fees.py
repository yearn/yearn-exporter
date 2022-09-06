
from typing import Optional
from brownie import chain
from yearn.entities import TreasuryTx, TxGroup
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
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
    return any(
        tx.from_address.address == vault.vault.address 
        and tx.token.address.address == vault.vault.address
        and tx.to_address.address in treasury.addresses
        and tx.to_address.address == vault.vault.rewards(block_identifier=tx.block)
        for vault in v2.vaults + v2.experiments
    )

def is_fees_v3(tx: TreasuryTx) -> bool:
    # Stay tuned...
    return False

def is_yearn_fed_fees(tx: TreasuryTx) -> bool:
    yearn_fed_strats = "0x09F61718474e2FFB884f438275C0405E3D3559d3", "0x7928becDda70755B9ABD5eE7c7D5E267F1412042", "0x09F61718474e2FFB884f438275C0405E3D3559d3"
    if tx._symbol in ["yvCurve-DOLA-U", "yveCRV-DAO"] and tx.from_address.address in yearn_fed_strats and tx.to_address and tx.to_address.address in treasury.addresses:
        return True

def is_temple(tx: TreasuryTx) -> bool:
    if tx._to_nickname == "Yearn Treasury":
        if tx._from_nickname == "Contract: StrategyConvexCrvCvxPairsClonable" and tx._symbol == "CRV":
            return True
        elif tx._from_nickname == "Contract: Splitter" and tx._symbol == "yveCRV-DAO":
            return True
