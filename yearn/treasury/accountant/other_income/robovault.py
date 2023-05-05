

from typing import Optional

from brownie import chain
from y.networks import Network

from yearn.entities import TreasuryTx, TxGroup
from yearn.treasury.accountant.constants import treasury
from yearn.utils import contract


def is_robovault_share(tx: TreasuryTx) -> Optional[TxGroup]:
    """
    After Yearn devs helped robovault with a vulnerability, robovault committed to sending Yearn a portion of their fees.
    """
    if chain.id != Network.Fantom:
        return False
        
    if not (
        tx.to_address and tx.to_address.address in treasury.addresses
        and tx._symbol.startswith('rv')
        and tx.from_address.is_contract
    ):
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
    if tx._from_nickname == "Contract: teamWallet" and tx.amount == 0:
        return True

    return all([
        tx._from_nickname == "Contract: Strategy",
        tx._symbol == 'rv3USDCc',
        contract(strat.vault(block_identifier = tx.block)).symbol() == 'rv3USDCb'
    ])
