
from brownie import Contract
from brownie.exceptions import ContractNotFound
from tqdm import tqdm
from y.networks import Network

from yearn.entities import Address
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
def __get_contracts() -> List[Address]:
    return select(a for a in Address if a.is_contract and a.chain.chainid == chain.id)


@db_session
def __ensure_topics_are_known(addresses: List[Address]) -> None:
    no_topics = [] 
    for address in tqdm(addresses):
        try:
            if not contract(address.address).topics:
                if not force_gnosis_safe_abi(address):
                    no_topics.append(address)
        except ContractNotFound:
            # This is MOST LIKELY unimportant and not Yearn related.
            logger.debug(f"{address.address} self destructed")
        except ValueError as e:
            if str(e).startswith("Source for") and str(e).endswith("has not been verified"):
                continue
            if "Contract source code not verified" in str(e):
                continue
            raise

    no_topics_with_nick = {address.nickname for address in no_topics if address.nickname}
    no_topics_no_nick = [address for address in no_topics if not address.nickname]
    if no_topics_with_nick:
        print("can't find topics for nicknames:")
        for nickname in no_topics_with_nick:
            print(nickname)
    if no_topics_no_nick:
        print("can't find topics for addresses:")
        for address in no_topics_no_nick:
            print(address)


@db_session
def __ensure_signatures_are_known(addresses: List[Address]) -> None:
    no_sigs = []
    for address in tqdm(addresses):
        try:
            if not contract(address.address).signatures:
                if not force_gnosis_safe_abi(address):
                    no_sigs.append(address)
        except ContractNotFound:
            # This is MOST LIKELY unimportant and not Yearn related.
            logger.debug(f"{address.address} self destructed")
        except ValueError as e:
            if str(e).startswith("Source for") and str(e).endswith("has not been verified"):
                continue
            if "Contract source code not verified" in str(e):
                continue
            raise

    no_sigs_with_nick = {address.nickname for address in no_sigs if address.nickname}
    no_sigs_no_nick = [address for address in no_sigs if not address.nickname]
    if no_sigs_with_nick:
        print("can't find signatures for nicknames:")
        for nickname in no_sigs_with_nick:
            print(nickname)
    if no_sigs_no_nick:
        print("can't find signatures for addresses:")
        for address in no_sigs_no_nick:
            print(address)


def force_gnosis_safe_abi(address: Address) -> bool:
    if GNOSIS_ABI and address.nickname in ["Contract: GnosisSafeProxy","Yearn Treasury","Yearn yChad Multisig"]:
        Contract.from_abi('GnosisSafeProxy',address.address,GNOSIS_ABI)
        return True
    return False


@db_session
def load():
    prepare_db()
    # Gnosis safes made me do this. In the future, so might other things.
    contracts = __get_contracts()
    #__ensure_topics_are_known(contracts)
    #__ensure_signatures_are_known(contracts)
load()
