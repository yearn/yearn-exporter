from collections import defaultdict
from itertools import count, product
from operator import itemgetter
from typing import Any, List, Optional
from urllib.error import HTTPError

import requests
from brownie import chain, web3
from eth_abi.exceptions import InsufficientDataBytes

from yearn.exceptions import MulticallError
from yearn.networks import Network
from yearn.typing import Block
from yearn.utils import contract, contract_creation_block

MULTICALL2 = {
    Network.Mainnet: '0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696',
    Network.Gnosis: '0xFAa296891cA6CECAF2D86eF5F7590316d0A17dA0', # maker has not yet deployed multicall2. This is from another deployment
    Network.Fantom: '0xD98e3dBE5950Ca8Ce5a4b59630a5652110403E5c',
    Network.Arbitrum: '0x5B5CFE992AdAC0C9D48E05854B2d91C73a003858',
}
multicall2 = contract(MULTICALL2[chain.id])


def fetch_multicall(*calls, block: Optional[Block] = None, require_success: bool = False) -> List[Any]:
    # https://github.com/makerdao/multicall
    multicall_input = []
    attribute_errors = []
    fn_list = []
    decoded = []

    for i, (contract, fn_name, *fn_inputs) in enumerate(calls):
        try:
            fn = getattr(contract, fn_name)

            # check that there aren't multiple functions with the same name
            if hasattr(fn, "_get_fn_from_args"):
                fn = fn._get_fn_from_args(fn_inputs)

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
    except (HTTPError, ValueError) as e:
        if 'out of gas' in str(e) or "Request Entity Too Large for url" in str(e):
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


def multicall_matrix(contracts, params, block="latest"):
    matrix = list(product(contracts, params))
    calls = [[contract, param] for contract, param in matrix]

    results = fetch_multicall(*calls, block=block)

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

    response = requests.post(web3.provider.endpoint_uri, json=jsonrpc_batch).json()
    return [
        fn.decode_output(res['result']) if res['result'] != '0x' else None
        for res in sorted(response, key=itemgetter('id'))
    ]
