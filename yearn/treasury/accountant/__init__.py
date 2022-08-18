
from brownie import Contract
from yearn.entities import Address
from yearn.networks import Network
from yearn.treasury.accountant.accountant import *
from yearn.treasury.accountant.prepare_db import prepare_db
from yearn.utils import contract

__all__ = [
    "all_txs",
    "unsorted_txs",
    "pending_txgroup",
    "sort_tx",
    "sort_txs",
    "get_txgroup",
    "describe_entity",
]


GNOSIS_IMPLEMENTATION = {
    # Version 1.3.0
    Network.Mainnet: "0xDaB5dc22350f9a6Aff03Cf3D9341aAD0ba42d2a6",
    Network.Fantom: "0xd9db270c1b5e3bd161e8c8503c55ceabee709552",
}.get(chain.id,None)

GNOSIS_ABI = contract(GNOSIS_IMPLEMENTATION).abi if GNOSIS_IMPLEMENTATION else None


@db_session
def get_addresses() -> List[Address]:
    return select(a for a in Address if a.is_contract and a.chain.chainid == chain.id)


@db_session
def ensure_topics_are_known(addresses: List[Address]) -> None:
    no_topics = []
    for address in addresses:
        if not contract(address.address).topics:
            if not get_deets(address):
                no_topics.append(address)

    print("can't find topics for nicknames:")
    for nickname in {address.nickname for address in no_topics if address.nickname}:
        print(nickname)
    
    print("can't find topics for addresses:")
    for address in [address for address in no_topics if not address.nickname]:
        print(address)


@db_session
def ensure_signatures_are_known(addresses: List[Address]) -> None:
    no_sigs = []
    for address in addresses:
        if not contract(address.address).signatures:
            if not get_deets(address):
                no_sigs.append(address)

    print("can't find signatures for nicknames:")
    for nickname in {address.nickname for address in no_sigs if address.nickname}:
        print(nickname)
    
    print("can't find signatures for addresses:")
    for address in [address for address in no_sigs if not address.nickname]:
        print(address)


def get_deets(address: Address) -> bool:
    if GNOSIS_ABI and address.nickname in ["Contract: GnosisSafeProxy","Yearn Treasury","Yearn yChad Multisig"]:
        Contract.from_abi('GnosisSafeProxy',address.address,GNOSIS_ABI)
        return True
    return False


@db_session
def load():
    prepare_db()
    addresses = get_addresses()
    ensure_topics_are_known(addresses)
    ensure_signatures_are_known(addresses)
    get_deets()
