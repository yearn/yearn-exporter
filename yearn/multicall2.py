from collections import defaultdict
from itertools import count, product
from operator import itemgetter

import requests
from brownie import Contract, chain, web3
from eth_abi.exceptions import InsufficientDataBytes

from yearn.networks import Network
from yearn.utils import contract_creation_block, contract

MULTICALL2 = {
    Network.Mainnet: '0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696',
    Network.Fantom: '0xD98e3dBE5950Ca8Ce5a4b59630a5652110403E5c',
    Network.Arbitrum: '0x5B5CFE992AdAC0C9D48E05854B2d91C73a003858',
}
multicall2 = contract(MULTICALL2[chain.id])


def fetch_multicall(*calls, block=None):
    # https://github.com/makerdao/multicall
    multicall_input = []
    fn_list = []
    decoded = []

    for contract, fn_name, *fn_inputs in calls:
        fn = getattr(contract, fn_name)

        # check that there aren't multiple functions with the same name
        if hasattr(fn, "_get_fn_from_args"):
            fn = fn._get_fn_from_args(fn_inputs)

        fn_list.append(fn)
        multicall_input.append((contract, fn.encode_input(*fn_inputs)))

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

    for fn, (ok, data) in zip(fn_list, result):
        try:
            assert ok, "call failed"
            decoded.append(fn.decode_output(data))
        except (AssertionError, InsufficientDataBytes):
            decoded.append(None)

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
                    block,
                ],
            }
        )

    response = requests.post(web3.provider.endpoint_uri, json=jsonrpc_batch).json()
    return [
        fn.decode_output(res['result']) if res['result'] != '0x' else None
        for res in sorted(response, key=itemgetter('id'))
    ]
