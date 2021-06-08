from brownie import chain, web3
from joblib import Parallel, delayed
from toolz import concat
from web3.middleware.filter import block_ranges
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from yearn.cache import memory

BATCH_SIZE = 1000


@memory.cache()
def _trace_filter(filter_params):
    return web3.manager.request_blocking('trace_filter', [filter_params])


def trace_filter(from_address, to_address, from_block, to_block):
    filter_params = {
        'fromAddress': from_address if isinstance(from_address, list) else [from_address],
        'toAddress': to_address if isinstance(to_address, list) else [to_address],
        'fromBlock': hex(from_block) if from_block else None,
        'toBlock': hex(to_block) if to_block else None,
    }
    return _trace_filter(filter_params)


def get_traces(from_address, to_address):
    """
    Compute all traces matching from_address OR to_address.
    """
    ranges = list(block_ranges(0, chain.height, BATCH_SIZE))
    pool = ThreadPoolExecutor()
    print(f'fetching traces in {len(ranges)} batches with {pool._max_workers} workers')
    task = lambda block_range: trace_filter(from_address, to_address, block_range[0], block_range[1])
    traces = []
    progress = tqdm(total=chain.height)
    for result in pool.map(task, ranges):
        traces.extend(result)
        if result:
            progress.update(result[-1]['blockNumber'] - progress.n)
            progress.set_postfix({'traces': len(traces)})
    
    progress.close()
    return traces

from brownie import Contract
from brownie.network.contract import get_type_strings

def format_function(fn):
    types_list = get_type_strings(fn.abi["inputs"], {"fixed168x10": "decimal"})
    return f"{fn.abi['name']}({','.join(x for x in types_list)})"


def decode_traces(traces):
    decoded = []
    targets = {x['action']['to'] for x in traces if x['type'] == 'call'}
    contracts = {x: Contract(x) for x in targets}
    for x in tqdm(traces):
        if 'error' in x or x['type'] != 'call' or x['action']['callType'] == 'staticcall' or x['action']['input'] == '0x':
            continue
        contract = contracts[x['action']['to']]
        try:
            func, args = contract.decode_input(x['action']['input'])
        except ValueError:
            Contract.from_explorer(str(contract))
            print(x)
            raise
        fn = contract.get_method_object(x['action']['input'])
        func = format_function(fn)
        output = fn.decode_output(x['result']['output'])
        decoded.append({
            'block': x['blockNumber'],
            'from': x['action']['from'],
            'to': x['action']['to'],
            'func': func,
            'args': args,
            'output': output,
            'gas_used': int(x['result']['gasUsed'], 16),
            'tx_hash': x['transactionHash'],
        })
    return decoded
