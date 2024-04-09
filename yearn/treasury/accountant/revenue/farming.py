
from brownie import ZERO_ADDRESS
from y import Contract

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury


def is_sex(tx: TreasuryTx) -> bool:
    sex_distributors = [
        ZERO_ADDRESS,
        # StakingRewards
        "0x7FcE87e203501C3a035CbBc5f0Ee72661976D6E1",
    ]
    if tx._symbol == "SEX" and tx.from_address.address in sex_distributors and tx.to_address and tx.to_address.address in treasury.addresses:
        return True
    return False

def is_solid(tx: TreasuryTx) -> bool:
    solid_distributors = [
        # StakingRewards
        "0x7FcE87e203501C3a035CbBc5f0Ee72661976D6E1",
        # LpDepositor
        "0x26E1A0d851CF28E697870e1b7F053B605C8b060F",
    ]
    if tx._symbol == "SOLID" and tx.from_address.address in solid_distributors and tx.to_address and tx.to_address.address in treasury.addresses:
        return True
    return False

def is_solidsex(tx: TreasuryTx) -> bool:
    solidsex_distributors = [
        # StakingRewards
        "0x7FcE87e203501C3a035CbBc5f0Ee72661976D6E1",
        # FeeDistributor
        "0xA5e76B97e12567bbA2e822aC68842097034C55e7",
    ]
    if tx._symbol == "SOLIDsex" and tx.from_address.address in solidsex_distributors and tx.to_address and tx.to_address.address in treasury.addresses:
        return True
    return False

def is_generic_comp_rewards(tx: TreasuryTx) -> bool:
    if tx.to_address and tx.to_address.address in treasury.addresses and "DistributedSupplierComp" in tx._events:
        for event in tx._events["DistributedSupplierComp"]:
            if tx.from_address.address == event.address and 'supplier' in event and event['supplier'] == tx.to_address.address:
                troller = Contract(event.address)
                if hasattr(troller, 'getCompAddress') and troller.getCompAddress() == tx.token.address.address:
                    return True

def is_comp_rewards(tx: TreasuryTx) -> bool:
    if tx._symbol == "COMP" and is_generic_comp_rewards(tx):
        return True

def is_scream_rewards(tx: TreasuryTx) -> bool:
    if tx._symbol == "SCREAM" and is_generic_comp_rewards(tx):
        return True

