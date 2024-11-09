
from brownie import chain
from y import Network

from yearn.entities import TreasuryTx


def is_seasolver_slippage_revenue(tx: TreasuryTx) -> bool:
    return chain.id == Network.Mainnet and tx._from_nickname == "Contract: TradeHandler" and tx._to_nickname == "yMechs Multisig"

def is_cowswap_incentive(tx: TreasuryTx) -> bool:
    """ Incentives for swapping on CowSwap """
    return tx._symbol == "COW" and tx.from_address == "0xA03be496e67Ec29bC62F01a428683D7F9c204930"