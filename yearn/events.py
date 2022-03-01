import logging
from collections import Counter, defaultdict
from itertools import zip_longest

from brownie import web3, chain
from brownie.network.event import EventDict, _decode_logs, _add_deployment_topics
from joblib import Parallel, delayed
from toolz import groupby
from web3.middleware.filter import block_ranges

from yearn.middleware.middleware import BATCH_SIZE
from yearn.utils import contract_creation_block, contract

logger = logging.getLogger(__name__)


def decode_logs(logs) -> EventDict:
    """
    Decode logs to events and enrich them with additional info.
    """
    decoded = _decode_logs(logs)
    for i, log in enumerate(logs):
        setattr(decoded[i], "block_number", log["blockNumber"])
        setattr(decoded[i], "transaction_hash", log["transactionHash"])
        setattr(decoded[i], "log_index", log["logIndex"])
        setattr(decoded[i], "address", log["address"])
    return decoded


def create_filter(address, topics=None):
    """
    Create a log filter for one or more contracts.
    Set fromBlock as the earliest creation block.
    """
    if address is None:
        # Treasury didn't exist prior to block 10502337
        return web3.eth.filter({"fromBlock": 10502337, "topics": topics}) 

    if isinstance(address, list):
        for a in address:
            add_deployment_topics(a)
        start_block = min(map(contract_creation_block, address))
    else:
        add_deployment_topics(address)
        start_block = contract_creation_block(address)

    return web3.eth.filter({"address": address, "fromBlock": start_block, "topics": topics})


def add_deployment_topics(address):
    _add_deployment_topics(address, contract(address).abi)


def get_logs_asap(address, topics, from_block=None, to_block=None, verbose=0):
    logs = []

    if from_block is None:
        from_block = contract_creation_block(address)
    if to_block is None:
        to_block = chain.height

    ranges = list(block_ranges(from_block, to_block, BATCH_SIZE[chain.id]))
    if verbose > 0:
        logger.info('fetching %d batches', len(ranges))

    batches = Parallel(8, "threading", verbose=verbose)(
        delayed(web3.eth.get_logs)({"address": address, "topics": topics, "fromBlock": start, "toBlock": end})
        for start, end in ranges
    )
    for batch in batches:
        logs.extend(batch)

    return logs


def logs_to_balance_checkpoints(logs):
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


def checkpoints_to_weight(checkpoints, start_block, end_block):
    total = 0
    for a, b in zip_longest(list(checkpoints), list(checkpoints)[1:]):
        if a < start_block or a > end_block:
            continue
        b = min(b, end_block) if b else end_block
        total += checkpoints[a] * (b - a) / (end_block - start_block)
    return total
