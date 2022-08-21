import json
import logging
import threading
from functools import lru_cache
from typing import List

import eth_retry
from brownie import Contract, chain, convert, interface, web3
from brownie.network.contract import _fetch_from_explorer, _resolve_address

from yearn.cache import memory
from yearn.exceptions import ArchiveNodeRequired, NodeNotSynced
from yearn.networks import Network
from yearn.typing import AddressOrContract

logger = logging.getLogger(__name__)

BINARY_SEARCH_BARRIER = {
    Network.Mainnet: 0,
    Network.Gnosis: 15_659_482, # gnosis returns "No state available for block 0x3f9e020290502d1d41f4b5519e7d456f0935dea980ec310935206cac8239117e"
    Network.Fantom: 4_564_024,  # fantom returns "missing trie node" before that
    Network.Arbitrum: 0,
    Network.Optimism: 0,
}

_erc20 = lru_cache(maxsize=None)(interface.ERC20)

PREFER_INTERFACE = {
    Network.Arbitrum: {
        "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f": _erc20, # empty ABI for WBTC when compiling the contract
    }
}

def safe_views(abi: List) -> List[str]:
    return [
        item["name"]
        for item in abi
        if item["type"] == "function"
        and item["stateMutability"] == "view"
        and not item["inputs"]
        and all(x["type"] in ["uint256", "bool"] for x in item["outputs"])
    ]


@memory.cache()
def get_block_timestamp(height):
    """
    An optimized variant of `chain[height].timestamp`
    """
    if chain.id == Network.Mainnet:
        try:
            header = web3.manager.request_blocking(f"erigon_getHeaderByNumber", [height])
            return int(header.timestamp, 16)
        except:
            pass
    return chain[height].timestamp


@memory.cache()
def closest_block_after_timestamp(timestamp: int) -> int:
    logger.debug('closest block after timestamp %d', timestamp)
    height = chain.height
    lo, hi = 0, height

    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        if get_block_timestamp(mid) > timestamp:
            hi = mid
        else:
            lo = mid

    if get_block_timestamp(hi) < timestamp:
        raise IndexError('timestamp is in the future')

    return hi


def get_code(address, block=None):
    try:
        return web3.eth.get_code(address, block_identifier=block)
    except ValueError as exc:
        if isinstance(exc.args[0], dict) and 'missing trie node' in exc.args[0]['message']:
            raise ArchiveNodeRequired('querying historical state requires an archive node')
        raise exc


@memory.cache()
def contract_creation_block(address: AddressOrContract) -> int:
    """
    Find contract creation block using binary search.
    NOTE Requires access to historical state. Doesn't account for CREATE2 or SELFDESTRUCT.
    """
    logger.info("contract creation block %s", address)
    address = convert.to_address(address)

    barrier = BINARY_SEARCH_BARRIER[chain.id]
    lo = barrier
    hi = end = chain.height

    if hi == 0:
        raise NodeNotSynced(f'''
            `chain.height` returns 0 on your node, which means it is not fully synced.
            You can only use contract_creation_block on a fully synced node.''')

    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        try:
            code = get_code(address, block=mid)
        except ArchiveNodeRequired as exc:
            logger.error(exc)
            # with no access to historical state, we'll have to scan logs from start
            return 0
        except ValueError as exc:
            # ValueError occurs in gnosis when there is no state for a block
            # with no access to historical state, we'll have to scan logs from start
            logger.error(exc) 
            return 0
        if code:
            hi = mid
        else:
            lo = mid

    # only happens on fantom
    if hi == barrier + 1:
        logger.warning('could not determine creation block for a contract deployed prior to barrier')
        return 0

    return hi if hi != end else None


class Singleton(type):
    def __init__(self, *args, **kwargs):
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
            return self.__instance
        else:
            return self.__instance


# cached Contract instance, saves about 20ms of init time
_contract_lock = threading.Lock()
_contract = lru_cache(maxsize=None)(Contract)

@eth_retry.auto_retry
def contract(address: AddressOrContract) -> Contract:
    with _contract_lock:
        address = web3.toChecksumAddress(str(address))

        if chain.id in PREFER_INTERFACE:
            if address in PREFER_INTERFACE[chain.id]:
                _interface = PREFER_INTERFACE[chain.id][address]
                i = _interface(address)
                return _squeeze(i)

        # autofetch-sources: false
        # Try to fetch the contract from the local sqlite db.
        try:
            c = _contract(address)
        # If we don't already have the contract in the db, we'll try to fetch it from the explorer.
        except ValueError as e:
            c = _resolve_proxy(address)

        # Lastly, get rid of unnecessary memory-hog properties
        return _squeeze(c)


# These tokens have trouble when resolving the implementation via the chain.
FORCE_IMPLEMENTATION = {
    Network.Mainnet: {
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "0xa2327a938Febf5FEC13baCFb16Ae10EcBc4cbDCF", # USDC as of 2022-08-10
    },
}.get(chain.id, {})

@eth_retry.auto_retry
def _resolve_proxy(address):
    name, abi, implementation = _extract_abi_data(address)
    as_proxy_for = None

    if address in FORCE_IMPLEMENTATION:
        implementation = FORCE_IMPLEMENTATION[address]
        name, abi, _ = _extract_abi_data(implementation)
        return Contract.from_abi(name, address, abi)

    # always check for an EIP1967 proxy - https://eips.ethereum.org/EIPS/eip-1967
    implementation_eip1967 = web3.eth.get_storage_at(
        address, int(web3.keccak(text="eip1967.proxy.implementation").hex(), 16) - 1
    )
    # always check for an EIP1822 proxy - https://eips.ethereum.org/EIPS/eip-1822
    implementation_eip1822 = web3.eth.get_storage_at(address, web3.keccak(text="PROXIABLE"))

    # Just leave this code where it is for a helpful debugger as needed.
    if address == "":
        raise Exception(
            f"""implementation: {implementation}
            implementation_eip1967: {len(implementation_eip1967)} {implementation_eip1967}
            implementation_eip1822: {len(implementation_eip1822)} {implementation_eip1822}""")

    if len(implementation_eip1967) > 0 and int(implementation_eip1967.hex(), 16):
        as_proxy_for = _resolve_address(implementation_eip1967[-20:])
    elif len(implementation_eip1822) > 0 and int(implementation_eip1822.hex(), 16):
        as_proxy_for = _resolve_address(implementation_eip1822[-20:])
    elif implementation:
        # for other proxy patterns, we only check if etherscan indicates
        # the contract is a proxy. otherwise we could have a false positive
        # if there is an `implementation` method on a regular contract.
        try:
            # first try to call `implementation` per EIP897
            # https://eips.ethereum.org/EIPS/eip-897
            c = Contract.from_abi(name, address, abi)
            as_proxy_for = c.implementation.call()
        except Exception:
            # if that fails, fall back to the address provided by etherscan
            as_proxy_for = _resolve_address(implementation)

    if as_proxy_for:
        name, abi, _ = _extract_abi_data(as_proxy_for)
    return Contract.from_abi(name, address, abi)


def _extract_abi_data(address):
    data = _fetch_from_explorer(address, "getsourcecode", False)
    is_verified = bool(data["result"][0].get("SourceCode"))
    if not is_verified:
        raise ValueError(f"Contract source code not verified: {address}")
    name = data["result"][0]["ContractName"]
    abi = json.loads(data["result"][0]["ABI"])
    implementation = data["result"][0].get("Implementation")
    return name, abi, implementation


@lru_cache(maxsize=None)
def is_contract(address: str) -> bool:
    '''checks to see if the input address is a contract'''
    return web3.eth.get_code(address) not in ['0x',b'']


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _squeeze(it):
    """ Reduce the contract size in RAM significantly. """
    for k in ["ast", "bytecode", "coverageMap", "deployedBytecode", "deployedSourceMap", "natspec", "opcodes", "pcMap"]:
        if it._build and k in it._build.keys():
            it._build[k] = {}
    return it
