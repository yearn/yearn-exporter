
import logging
from time import time
from typing import Any, Dict, Iterable, List, Optional

from brownie import chain
from pony.orm import Set, commit, db_session, select
from pony.orm.core import Entity
from tqdm import tqdm
from yearn.entities import Chain, TreasuryTx, TxGroup
from yearn.outputs.postgres.utils import cache_txgroup
#from yearn.treasury.accountant.cost_of_revenue import cost_of_revenue
#from yearn.treasury.accountant.expenses import expenses
from yearn.treasury.accountant.fees import fees
from yearn.treasury.accountant.ignore import ignore
from yearn.treasury.accountant.other_income import other_income

PENDING_LABEL = "Categorization Pending"

logger = logging.getLogger(__name__)
    

""" Accountant sorts treasury transactions into the appropriate categories for real-time transparent reporting. """

top_level_txgroups = [
    fees,
    #cost_of_revenue,
    #expenses,
    other_income,
    ignore,
]


def pending_txgroup() -> TxGroup:
    """ Returns the TxGroup used for transactions awaiting categorization. """
    return cache_txgroup(PENDING_LABEL)


@db_session
def unsorted_txs() -> List[TreasuryTx]:
    """ Returns all unsorted txs for the current chain. """
    return select(tx for tx in TreasuryTx if tx.chain.chainid == chain.id and tx.txgroup.name == PENDING_LABEL) #'0xfa116AB2137c81811B0198d59a51BD7c1c32659C' in [tx.from_address.address, tx.to_address.address] ) # and not tx.token.symbol.startswith('rv')) # and tx.token.symbol == 'CRV')


@db_session
def all_txs(all_chains: bool = False) -> List[TreasuryTx]:
    """
    If `all_chains` is True, returns all transactions in postgres.
    If `all_chains` is False, returns all transactions for the current chain.
    """
    start = time()
    if all_chains:
        txs = select(tx for tx in TreasuryTx)
    else:
        txs = select(tx for tx in TreasuryTx if tx.chain.chainid == chain.id)
    logger.info(f"Loaded {len(txs)} in {round(time()-start,2)}s")
    return txs


def sort_tx(tx: Optional[TreasuryTx]) -> Optional[TxGroup]:
    """ Sorts a TreasuryTx `tx` into the appropriate TxGroup. """
    txgroup = get_txgroup(tx)
    if txgroup != tx.txgroup:
        tx.txgroup = txgroup
    return txgroup


def sort_txs(txs: Iterable[TreasuryTx]) -> None:
    """ Sorts each TreasuryTx in `txs` into the appropriate TxGroup. """

    start = time()
    start_len = len(txs)
    i = 0
    for tx in tqdm(txs):
        sort_tx(tx)
        if i / 10 == i // 10:
            commit()

    logger.info(f"sorted {start_len} transactions in {round(time()-start,2)}s")


def get_txgroup(tx: Optional[TreasuryTx]) -> Optional[TxGroup]:
    """ Returns the appropriate TxGroup for TreasuryTx `tx`. """
    if tx is None:
        return pending_txgroup()
    for segment in top_level_txgroups:
        txgroup = segment.sort(tx)
        if txgroup:
            return txgroup
    return pending_txgroup()


def describe_entity(e: Entity, recursion_depth: int = 0) -> Dict[str,Any]:
    """ Iterively unwraps a pony orm Entity into a dict. """

    # This just ensures all attributes are in memory.
    e.to_dict()

    max_recursions = 2
    return {
        k: describe_entity(v, recursion_depth + 1) if isinstance(v, Entity) and recursion_depth < max_recursions else v
        for k, v
        in e._vals_.items()
        if v 
        and type(k) != Set
        # We only need chain infos on first recursion
        and (recursion_depth == 0 or not isinstance(v, Chain))
    }
