import logging
from collections import Counter, defaultdict
from itertools import zip_longest
from typing import Dict, List, Optional, Union

from brownie import chain, web3
from brownie.network.event import (EventDict, _add_deployment_topics,
                                   _decode_logs)
from joblib import Parallel, delayed
from toolz import groupby
from web3.middleware.filter import block_ranges
from web3.types import LogReceipt, RPCEndpoint

from yearn.middleware.middleware import BATCH_SIZE
from yearn.typing import Address, Block, Topics
from yearn.utils import contract, contract_creation_block

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


def create_filter(address: Address, topics: Optional[Topics] = None) -> RPCEndpoint:
    """
    Create a log filter for one or more contracts.
    Set fromBlock as the earliest creation block.
    """
    if isinstance(address, list):
        start_block = min(map(contract_creation_block, address))
    else:
        start_block = contract_creation_block(address)

    return web3.eth.filter({"address": address, "fromBlock": start_block, "topics": topics})


def __add_deployment_topics(address: Address) -> None:
    _add_deployment_topics(address, contract(address).abi)


def get_logs_asap(
    addresses: Optional[Union[Address,List[Address]]],
    topics: Optional[Topics],
    from_block: Optional[Block] = None,
    to_block: Optional[Block] = None,
    verbose: int = 0
    ) -> List[LogReceipt]:

    logs = []

    if from_block is None:
        if type(addresses) == list:
            min(map(lambda address: contract_creation_block(address), addresses))
        elif addresses:
            from_block = contract_creation_block(addresses)
        else:
            from_block = 0

    if to_block is None:
        to_block = chain.height

    ranges = list(block_ranges(from_block, to_block, BATCH_SIZE[chain.id]))
    if verbose > 0:
        logger.info('fetching %d batches', len(ranges))

    batches = Parallel(8, "threading", verbose=verbose)(
        delayed(web3.eth.get_logs)({"address": addresses, "topics": topics, "fromBlock": start, "toBlock": end})
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
