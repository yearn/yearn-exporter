import asyncio
import os
from collections import defaultdict
from itertools import count, product
from operator import itemgetter
from typing import Any, List, Optional

import requests
from brownie import Contract, chain, web3
from brownie.network.contract import _ContractMethod
from eth_abi.exceptions import InsufficientDataBytes

from yearn.exceptions import MulticallError
from yearn.networks import Network
from yearn.typing import Block
from yearn.utils import contract, contract_creation_block

JSONRPC_BATCH_MAX_SIZE = int(os.environ.get("JSONRPC_BATCH_MAX_SIZE", 10_000)) # Currently set arbitrarily, necessaary for certain node-as-a-service providers.
MULTICALL_MAX_SIZE = int(os.environ.get("MULTICALL_MAX_SIZE", 500)) # Currently set arbitrarily
MULTICALL2 = {
    Network.Mainnet: '0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696',
    Network.Gnosis: '0xFAa296891cA6CECAF2D86eF5F7590316d0A17dA0', # maker has not yet deployed multicall2. This is from another deployment
    Network.Fantom: '0xD98e3dBE5950Ca8Ce5a4b59630a5652110403E5c',
    Network.Arbitrum: '0x5B5CFE992AdAC0C9D48E05854B2d91C73a003858',
    Network.Optimism: '0xcA11bde05977b3631167028862bE2a173976CA11' # Multicall 3
}
multicall2 = contract(MULTICALL2[chain.id])


def fetch_multicall(*calls, block: Optional[Block] = None, require_success: bool = False) -> List[Any]:
    # Before doing anything, make sure the load is manageable and size down if necessary.
    if (num_calls := len(calls)) > MULTICALL_MAX_SIZE:
        batches = [calls[i:i + MULTICALL_MAX_SIZE] for i in range(0, num_calls, MULTICALL_MAX_SIZE)]
        return [result for batch in batches for result in fetch_multicall(*batch, block=block, require_success=require_success)]
    
    # https://github.com/makerdao/multicall
    multicall_input = []
    attribute_errors = []
    fn_list = []
    decoded = []

    for i, (contract, fn_name, *fn_inputs) in enumerate(calls):
        try:
            fn = _get_fn(contract, fn_name, fn_inputs)
            fn_list.append(fn)
            multicall_input.append((contract, fn.encode_input(*fn_inputs)))
        except AttributeError:
            if not require_success:
                attribute_errors.append(i)
                continue
            raise

    try:
        if isinstance(block, int) and block < contract_creation_block(MULTICALL2[chain.id]):
            # use state override to resurrect the contract prior to deployment
            data = multicall2.tryAggregate.encode_input(False, multicall_input)
            call = web3.eth.call(
                {'to': str(multicall2), 'data': data},
                block or 'latest',
                {str(multicall2): {'code': f'0x{multicall2.bytecode}'}},
            )
            result = multicall2.tryAggregate.decode_output(call)
        else:
            result = multicall2.tryAggregate.call(
                False, multicall_input, block_identifier=block or 'latest'
            )
    except ValueError as e:
        if 'out of gas' in str(e) or 'execution aborted (timeout = 10s)' in str(e):
            halfpoint = len(calls) // 2
            batch0 = fetch_multicall(*calls[:halfpoint],block=block,require_success=require_success)
            batch1 = fetch_multicall(*calls[halfpoint:],block=block,require_success=require_success)
            return batch0 + batch1
        raise

    for fn, (ok, data) in zip(fn_list, result):
        try:
            assert ok, "call failed"
            decoded.append(fn.decode_output(data))
        except (AssertionError, InsufficientDataBytes):
            if require_success:
                raise MulticallError()
            decoded.append(None)

    # NOTE this will only run if `require_success` is True
    for i in attribute_errors:
        decoded.insert(i, None)

    return decoded

async def fetch_multicall_async(*calls, block: Optional[Block] = None, require_success: bool = False) -> List[Any]:
    # https://github.com/makerdao/multicall
    attribute_errors = []
    coros = []

    for i, (contract, fn_name, *fn_inputs) in enumerate(calls):
        try:
            fn = _get_fn(contract, fn_name, fn_inputs)
        except AttributeError as e:
            if require_success:
                raise AttributeError(e, contract, fn_name)
            attribute_errors.append(i)
            continue

        try:
            coros.append(fn.coroutine(*fn_inputs, block_identifier=block))
        except AttributeError as e:
            raise AttributeError(e, contract, fn_name)

    results = await asyncio.gather(*coros, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            if require_success:
                raise result
            else:
                results[i] = None

    # NOTE this will only run if `require_success` is True
    for i in attribute_errors:
        results.insert(i, None)

    return results

def _get_fn(contract: Contract, fn_name: str, fn_inputs: Any) -> _ContractMethod:
    fn = getattr(contract, fn_name)
    # check that there aren't multiple functions with the same name
    if hasattr(fn, "_get_fn_from_args"):
        fn = fn._get_fn_from_args(fn_inputs)
    return fn

def multicall_matrix(contracts, params, block="latest"):
    matrix = list(product(contracts, params))
    calls = [[contract, param] for contract, param in matrix]

    results = fetch_multicall(*calls, block=block)

    output = defaultdict(dict)
    for (contract, param), value in zip(matrix, results):
        output[contract][param] = value

    return dict(output)


async def multicall_matrix_async(contracts, params, block="latest"):
    matrix = list(product(contracts, params))
    calls = [[contract, param] for contract, param in matrix]

    results = await fetch_multicall_async(*calls, block=block)

    output = defaultdict(dict)
    for (contract, param), value in zip(matrix, results):
        output[contract][param] = value

    return dict(output)


def batch_call(calls):
    """
    Similar interface but block height as last param. Uses JSON-RPC batch.

    [[contract, 'func', arg, block_identifier]]
    """
    jsonrpc_batch = []
    fn_list = []
    ids = count()

    for contract, fn_name, *fn_inputs, block in calls:
        fn = getattr(contract, fn_name)
        if hasattr(fn, "_get_fn_from_args"):
            fn = fn._get_fn_from_args(fn_inputs)
        fn_list.append(fn)

        jsonrpc_batch.append(
            {
                'jsonrpc': '2.0',
                'id': next(ids),
                'method': 'eth_call',
                'params': [
                    {'to': str(contract), 'data': fn.encode_input(*fn_inputs)},
                    hex(block),
                ],
            }
        )
    
    chunks = [jsonrpc_batch[i:i+JSONRPC_BATCH_MAX_SIZE] for i in range(0, len(jsonrpc_batch), JSONRPC_BATCH_MAX_SIZE)]

    responses = [requests.post(web3.provider.endpoint_uri, json=jsonrpc_batch).json() for jsonrpc_batch in chunks]

    for response in responses:
        # A successful response will be a list
        if isinstance(response, dict) and 'result' in response and isinstance(response['result'], dict) and 'message' in response['result']:
            raise ValueError(response['result']['message'])
            
        for call_response in response:
            if 'error' in call_response:
                raise ValueError(call_response['error']['message'])

    response = [call_response for batch_response in responses for call_response in batch_response]

    return [
        fn.decode_output(res['result']) if res['result'] != '0x' else None
        for res in sorted(response, key=itemgetter('id'))
    ]
