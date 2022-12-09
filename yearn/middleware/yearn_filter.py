from typing import (
    Any,
    Callable,
    Union,
)

import eth_retry

from eth_utils import (
    apply_key_map
)

from web3._utils.rpc_abi import (
    RPC,
)
from web3.types import (  # noqa: F401
    RPCEndpoint,
    RPCResponse,
)

from web3.middleware.filter import (
    RequestLogs,
    RequestBlocks
)

from yearn.middleware.filter_manager import FilterManager


FILTER_PARAMS_KEY_MAP = {
    "toBlock": "to_block",
    "fromBlock": "from_block"
}

NEW_FILTER_METHODS = set([
    "eth_newBlockFilter",
    "eth_newFilter",
])

FILTER_CHANGES_METHODS = set([
    "eth_getFilterChanges",
    "eth_getFilterLogs",
])


def local_filter_middleware(
    make_request: Callable[[RPCEndpoint, Any], Any], w3: "Web3"
) -> Callable[[RPCEndpoint, Any], RPCResponse]:

    def middleware(method: RPCEndpoint, params: Any) -> RPCResponse:
        filter_man = FilterManager()

        if method in NEW_FILTER_METHODS:
            filter_id = filter_man.next_filter_id()
            _filter: Union[RequestLogs, RequestBlocks]
            if method == RPC.eth_newFilter:
                _filter = RequestLogs(w3, **apply_key_map(FILTER_PARAMS_KEY_MAP, params[0]))

            elif method == RPC.eth_newBlockFilter:
                _filter = RequestBlocks(w3)

            else:
                raise NotImplementedError(method)

            filter_man.add_filter(filter_id, _filter)
            return {"result": filter_id}

        elif method in FILTER_CHANGES_METHODS:
            filter_id = params[0]
            _filter = filter_man.get_filter(filter_id)
            #  Pass through to filters not created by middleware
            if _filter is None:
                return make_request(method, params)

            if method == RPC.eth_getFilterChanges:
                return {"result": next(_filter.filter_changes)}
            elif method == RPC.eth_getFilterLogs:
                # type ignored b/c logic prevents RequestBlocks which doesn't implement get_logs
                return {"result": eth_retry.auto_retry(_filter.get_logs)()}  # type: ignore
            else:
                raise NotImplementedError(method)
        else:
            return make_request(method, params)

    return middleware
