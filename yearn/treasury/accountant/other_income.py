


from typing import Optional

from brownie import chain
from yearn.entities import TreasuryTx, TxGroup
from yearn.networks import Network
from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.fees import treasury
from yearn.utils import contract

OTHER_INCOME_LABEL = "Other Income"
other_income = TopLevelTxGroup(OTHER_INCOME_LABEL)

def is_robovault_share(tx: TreasuryTx) -> Optional[TxGroup]:
    """
    After Yearn devs helped robovault with a vulnerability, robovault committed to sending Yearn a portion of their fees.
    """
    if not all([
        chain.id == Network.Fantom,
        tx.to_address and tx.to_address.address in treasury.addresses,
        tx.token.symbol.startswith('rv'),
        tx.from_address.is_contract,
    ]):
        return False
    
    try:
        strat = contract(tx.from_address.address)
    except ValueError as e:
        if not "Contract source code not verified" in str(e):
            raise
        return False
    
    if not hasattr(strat,'vault'):
        return False
    
    if strat.vault(block_identifier=tx.block) == tx.token.address.address:
        return True
    
    # For some reason these weren't caught by the above logic. Its inconsequential and not worth investigating to come up with better hueristics.
    if tx.from_address.nickname == "Contract: teamWallet" and tx.amount == 0:
        return True

    return all([
        tx.from_address.nickname == "Contract: Strategy",
        tx.token.symbol == 'rv3USDCc',
        contract(strat.vault(block_identifier = tx.block)).symbol() == 'rv3USDCb'
    ])


other_income.create_child("RoboVault Thank You", is_robovault_share)
