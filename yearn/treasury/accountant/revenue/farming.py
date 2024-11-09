
from brownie import ZERO_ADDRESS
from y import Contract

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury


_sex_distributors = [
    ZERO_ADDRESS,
    "0x7FcE87e203501C3a035CbBc5f0Ee72661976D6E1", # StakingRewards
]

_solid_distributors = [
    "0x7FcE87e203501C3a035CbBc5f0Ee72661976D6E1", # StakingRewards
    "0x26E1A0d851CF28E697870e1b7F053B605C8b060F", # LpDepositor
]

_solidsex_distributors = [
    "0x7FcE87e203501C3a035CbBc5f0Ee72661976D6E1", # StakingRewards
    "0xA5e76B97e12567bbA2e822aC68842097034C55e7", # FeeDistributor
]

def is_sex(tx: TreasuryTx) -> bool:
    return tx._symbol == "SEX" and tx.from_address in _sex_distributors and tx.to_address.address in treasury.addresses

def is_solid(tx: TreasuryTx) -> bool:
    return tx._symbol == "SOLID" and tx.from_address in _solid_distributors and tx.to_address.address in treasury.addresses

def is_solidsex(tx: TreasuryTx) -> bool:
    return tx._symbol == "SOLIDsex" and tx.from_address in _solidsex_distributors and tx.to_address.address in treasury.addresses

def is_generic_comp_rewards(tx: TreasuryTx) -> bool:
    if tx.to_address.address in treasury.addresses and "DistributedSupplierComp" in tx._events:
        for event in tx._events["DistributedSupplierComp"]:
            if tx.from_address == event.address and 'supplier' in event and tx.to_address == event['supplier']:
                troller = Contract(event.address)
                if hasattr(troller, 'getCompAddress') and troller.getCompAddress() == tx.token:
                    return True
    return False

def is_comp_rewards(tx: TreasuryTx) -> bool:
    return tx._symbol == "COMP" and is_generic_comp_rewards(tx)

def is_scream_rewards(tx: TreasuryTx) -> bool:
    return tx._symbol == "SCREAM" and is_generic_comp_rewards(tx)
