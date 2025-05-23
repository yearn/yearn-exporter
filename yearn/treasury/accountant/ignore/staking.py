
from brownie import ZERO_ADDRESS
from y import Network
from y.constants import CHAINID

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury


def is_solidex_staking(tx: TreasuryTx) -> bool:
    """ Used when tokens are staked in a staking contract. """
    # Solidex Finance: LP Depositor
    lp_depositor = "0x26E1A0d851CF28E697870e1b7F053B605C8b060F"

    # STAKING
    # Step 1: Stake your tokens
    if tx.from_address.address in treasury.addresses and tx.to_address == lp_depositor and "Deposited" in tx._events:
        for event in tx._events["Deposited"]:
            if event.address == lp_depositor and 'user' in event and 'pool' in event and tx.from_address == event['user'] and tx.token == event['pool']:
                return True
    
    # Step 2: Get your claim tokens
    elif tx.from_address == ZERO_ADDRESS and tx.to_address.address in treasury.addresses and "Deposited" in tx._events:
        for event in tx._events["Deposited"]:
            pool = tx.token.contract.pool()
            if event.address == lp_depositor and 'user' in event and 'pool' in event and tx.to_address == event['user'] and event['pool'] == pool:
                return True
    
    # UNSTAKING
    # Step 1: Burn your claim tokens
    elif tx.from_address.address in treasury.addresses and tx.to_address == ZERO_ADDRESS and "Withdrawn" in tx._events:
        token = tx.token.contract
        if hasattr(token, 'pool'):
            pool = token.pool()
            for event in tx._events["Withdrawn"]:
                if event.address == lp_depositor and 'user' in event and 'pool' in event and tx.from_address == event['user'] and event['pool'] == pool:
                    return True

    # Step 2: Unstake your tokens
    elif tx.from_address == lp_depositor and tx.to_address.address in treasury.addresses and "Withdrawn" in tx._events:
        for event in tx._events["Withdrawn"]:
            if event.address == lp_depositor and 'user' in event and 'pool' in event and tx.to_address == event['user'] and tx.token == event['pool']:
                return True
    
    return False

def is_curve_gauge(tx: TreasuryTx) -> bool:
    """ Not worth auto sorting now, could change in future if happens more often """
    hashes = {
        Network.Mainnet: [
            "0xfb9fbe6e6c1d6e3dbeae81f80f0ff7729c556b08afb6ce1fa8ab04d3ecb56788",
            "0x832eb508906baf2c00dfec7a2d3f7b856fdee683921a5fff206cf6b0c997cb32",
        ],
    }.get(CHAINID, [])
    return tx in HashMatcher(hashes)