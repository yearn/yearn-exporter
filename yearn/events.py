import itertools

from brownie import chain, web3
from brownie.network.event import EventDict
from brownie.network.event import _decode_logs as decode_logs
from joblib import Memory, Parallel, delayed

memory = Memory("cache", verbose=0)
web3.provider._request_kwargs["timeout"] = 600


def get_logs(address, from_block, to_block):
    return web3.eth.getLogs({"address": address, "fromBlock": from_block, "toBlock": to_block})


@memory.cache
def contract_creation_block(address) -> int:
    """
    Use binary search to determine the block when a contract was created.
    NOTE Requires access to archive state. A recommended option is Turbo Geth.
    """
    height = chain.height
    lo, hi = 0, height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if web3.eth.getCode(address, block_identifier=mid):
            hi = mid
        else:
            lo = mid
    return hi if hi != height else None


def fetch_events(address) -> EventDict:
    """
    Fetch all events emitted by a contract.
    Enriches events with additional data for further processing.
    """
    batch_size = 10_000
    from_block = contract_creation_block(str(address))
    to_block = chain.height
    args = [[start, min(start + batch_size - 1, to_block)] for start in range(from_block, to_block, batch_size)]
    tasks = Parallel(n_jobs=8, prefer="threads", verbose=10)(
        delayed(memory.cache(get_logs) if end < to_block else get_logs)(str(address), start, end) for start, end in args
    )
    logs = list(itertools.chain.from_iterable(tasks))
    decoded = decode_logs(logs)
    for i, log in enumerate(logs):
        setattr(decoded[i], "block_number", log["blockNumber"])
        setattr(decoded[i], "transaction_hash", log["transactionHash"])
        setattr(decoded[i], "log_index", log["logIndex"])
    return decoded
