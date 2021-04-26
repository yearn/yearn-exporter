import logging

from brownie import chain, web3
from brownie.network.event import EventDict, _decode_logs
from joblib import Parallel, delayed
from web3.middleware.filter import block_ranges

from yearn.middleware import BATCH_SIZE
from yearn.utils import contract_creation_block

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
    return decoded


def create_filter(address, topics=None):
    """
    Create a log filter for one or more contracts.
    Set fromBlock as the earliest creation block.
    """
    if isinstance(address, list):
        start_block = min(map(contract_creation_block, address))
    else:
        start_block = contract_creation_block(address)

    return web3.eth.filter({"address": address, "fromBlock": start_block, "topics": topics})


def get_logs_asap(address, topics, from_block, to_block):
    logs = []
    ranges = list(block_ranges(from_block, to_block, BATCH_SIZE))
    logger.info('fetching %d batches', len(ranges))
    batches = Parallel(8, "threading", verbose=10)(
        delayed(web3.eth.get_logs)({"address": address, "topics": topics, "fromBlock": start, "toBlock": end})
        for start, end in ranges
    )
    for batch in batches:
        logs.extend(batch)

    return logs
