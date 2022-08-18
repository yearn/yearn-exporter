

from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import ChildTxGroup, TopLevelTxGroup

OPEX_LABEL = "Operating Expenses"

expenses = TopLevelTxGroup(OPEX_LABEL)

def is_team_payment(tx: TreasuryTx) -> bool:
    hashes = {
        Network.Mainnet: [

        ],
    }.get(chain.id, [])
    disperse_app_hashes = {
        Network.Mainnet: [

        ]
    }

    if tx.hash in hashes:
        return True
    elif tx.hash in disperse_app_hashes and tx.from_address.label == 'Disperse.app':
        return True
    return False

expenses.create_child("Team Payments", is_team_payment)
