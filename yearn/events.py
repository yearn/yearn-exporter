import logging
from collections import Counter, defaultdict
from itertools import zip_longest
from typing import Any, Dict, List, Optional, Union

from brownie import chain, web3
from brownie.exceptions import ContractNotFound
from brownie.network.event import (EventDict, _add_deployment_topics,
                                   _decode_logs)
from joblib import Parallel, delayed
from toolz import groupby
from web3.middleware.filter import block_ranges
from web3.types import LogReceipt, RPCEndpoint
from y import Contract
from y.contracts import contract_creation_block

from yearn.middleware.middleware import BATCH_SIZE
from yearn.typing import Address, Block, Topics

logger = logging.getLogger(__name__)


def decode_logs(logs: List[LogReceipt]) -> EventDict:
    """
    Decode logs to events and enrich them with additional info.
    """
    addresses = {log.address for log in logs}
    for address in addresses:
        __add_deployment_topics(address)

    decoded = _decode_logs(logs)
    for i, log in enumerate(logs):
        setattr(decoded[i], "block_number", log["blockNumber"])
        setattr(decoded[i], "transaction_hash", log["transactionHash"])
        setattr(decoded[i], "log_index", log["logIndex"])
    return decoded


def __add_deployment_topics(address: Address) -> None:
    try:
        _add_deployment_topics(address, Contract(address).abi)
    except ContractNotFound:
        # This contract seems to have self destructed
        pass

def get_logs_asap(
    addresses: Optional[Union[Address,List[Address]]] = None,
    topics: Optional[Topics] = None,
    from_block: Optional[Block] = None,
    to_block: Optional[Block] = None,
    verbose: int = 0
    ) -> List[LogReceipt]:

    logs = []

    if from_block is None:
        if type(addresses) == list:
            from_block = min(map(contract_creation_block, addresses))
        elif addresses:
            from_block = contract_creation_block(addresses)
        else:
            from_block = 0

    if to_block is None:
        to_block = chain.height

    ranges = list(block_ranges(from_block, to_block, BATCH_SIZE))
    if verbose > 0:
        logger.info('fetching %d batches', len(ranges))

    batches = Parallel(64, "threading", verbose=verbose)(
        delayed(web3.eth.get_logs)(_get_logs_params(addresses, topics, start, end))
        for start, end in ranges
    )
    for batch in batches:
        logs.extend(batch)

    return logs


def logs_to_balance_checkpoints(logs: List[LogReceipt]) -> Dict[Address,Dict[Block,int]]:
    """
    Convert Transfer logs to `{address: {from_block: balance}}` checkpoints.
    """
    balances = Counter()
    checkpoints = defaultdict(dict)
    for block, block_logs in groupby('blockNumber', logs).items():
        events = decode_logs(block_logs)
        for log in events:
            # ZERO_ADDRESS tracks -totalSupply
            sender, receiver, amount = log.values()  # there can be several different aliases
            balances[sender] -= amount
            checkpoints[sender][block] = balances[sender]
            balances[receiver] += amount
            checkpoints[receiver][block] = balances[receiver]
    return checkpoints


def checkpoints_to_weight(checkpoints, start_block: Block, end_block: Block):
    total = 0
    for a, b in zip_longest(list(checkpoints), list(checkpoints)[1:]):
        if a < start_block or a > end_block:
            continue
        b = min(b, end_block) if b else end_block
        total += checkpoints[a] * (b - a) / (end_block - start_block)
    return total

def _get_logs_params(
    addresses: Optional[Union[Address,List[Address]]],
    topics: Optional[Topics],
    start: Block,
    end: Block
    ) -> Dict[str,Any]:
    params = {"fromBlock": start, "toBlock": end}
    if addresses:
        # pass in a list of addresses
        params["address"] = addresses
    if topics:
        params["topics"] = topics
    return params
