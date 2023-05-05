
from brownie import chain
from y import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher


def is_balancer_swap(tx: TreasuryTx) -> bool:
    return tx in HashMatcher({
        Network.Mainnet: [
            "0x1fc193ff95f0c147c9e653308cb92b379eb1c167e9d129e5b2e720d7c5703f1f",
        ],
    }.get(chain.id, []))
