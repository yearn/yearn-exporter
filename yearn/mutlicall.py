from brownie import Contract

multicall = Contract('0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441')


def fetch_multicall(*calls):
    multicall_input = []
    fn_list = []
    decoded = []

    for contract, fn_name, *fn_inputs in calls:
        fn = getattr(contract, fn_name)

        # check that there aren't multiple functions with the same name
        if hasattr(fn, '_get_fn_from_args'):
            fn = fn._get_fn_from_args(fn_inputs)

        fn_list.append(fn)

        multicall_input.append((contract, fn.encode_input(*fn_inputs)))

    response = multicall.aggregate.call(multicall_input)[1]

    for fn, data in zip(fn_list, response):
        decoded.append(fn.decode_output(data.hex()))

    return decoded
