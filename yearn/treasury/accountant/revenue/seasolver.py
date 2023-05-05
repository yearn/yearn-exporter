
from brownie import chain
from y import Network

from yearn.entities import TreasuryTx


def is_seasolver_slippage_revenue(tx: TreasuryTx) -> bool:
    return chain.id == Network.Mainnet and tx._from_nickname == "Contract: TradeHandler" and tx._to_nickname == "yMechs Multisig"
