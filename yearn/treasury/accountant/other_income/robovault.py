

from typing import Optional

from brownie import chain
from y import ContractNotVerified, ERC20, Network

from yearn.entities import TreasuryTx, TxGroup
from yearn.treasury.accountant.constants import treasury


def is_robovault_share(tx: TreasuryTx) -> Optional[TxGroup]:
    """
    After Yearn devs helped robovault with a vulnerability, robovault committed to sending Yearn a portion of their fees.
    """
    if chain.id != Network.Fantom:
        return False
        
    if not (
        tx.to_address.address in treasury.addresses
        and tx._symbol.startswith('rv')
        and tx.from_address.is_contract
    ):
        return False
    
    try:
        strat = tx.from_address.contract
    except ContractNotVerified:
        return False
    
    if not hasattr(strat,'vault'):
        return False
    
    if strat.vault(block_identifier=tx.block) == tx.token:
        return True
    
    # For some reason these weren't caught by the above logic. Its inconsequential and not worth investigating to come up with better hueristics.
    if tx._from_nickname == "Contract: teamWallet" and tx.amount == 0:
        return True

    return all([
        tx._from_nickname == "Contract: Strategy",
        tx._symbol == 'rv3USDCc',
        ERC20(strat.vault(block_identifier = tx.block)).symbol == 'rv3USDCb'
    ])
