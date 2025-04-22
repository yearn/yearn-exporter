import asyncio
import logging
import re
import time
from contextlib import suppress
from functools import cached_property
from typing import (TYPE_CHECKING, Any, AsyncIterator, Dict, List, NoReturn,
                    Optional, Union)

import a_sync
import dank_mids
from async_property import async_cached_property, async_property
from brownie import chain
from brownie.network.event import _EventItem
from eth_utils import encode_hex, event_abi_to_log_topic
from semantic_version.base import Version
from y import ERC20, Contract, Network, magic, get_price
from y.contracts import contract_creation_block_async
from y._decorators import stuck_coro_debugger
from y.exceptions import ContractNotVerified, PriceError, yPriceMagicError
from y.utils.events import ProcessedEvents

from yearn.common import Tvl
from yearn.multicall2 import fetch_multicall_async
from yearn.special import Ygov
from yearn.typing import Address
from yearn.utils import safe_views
from yearn.v2.strategies import Strategy

if TYPE_CHECKING:
    from yearn.apy.common import ApySamples

VAULT_VIEWS_SCALED = {
    "totalAssets",
    "maxAvailableShares",
    "pricePerShare",
    "debtOutstanding",
    "creditAvailable",
    "expectedReturn",
    "totalSupply",
    "availableDepositLimit",
    "depositLimit",
    "totalDebt",
    "debtLimit",
    "lockedProfit",
    "lockedProfitDegration",
}

# we are only interested in strategy-related events
STRATEGY_EVENTS = {
    "StrategyAdded",
    "StrategyMigrated",
    "StrategyRevoked",
    "StrategyReported",
}

logger = logging.getLogger(__name__)

async def get_price_return_exceptions(token, block=None):
    try:
        return await get_price(token, block=block, silent=True, sync=False)
    except Exception as e:
        return e

BORKED = {
    Network.Mainnet: [
        # borked in the vyper exploit of july 2023
        "0x718AbE90777F5B778B52D553a5aBaa148DD0dc5D",
        # price borked
        "0xc5F3D11580c41cD07104e9AF154Fc6428bb93c73",
        "0x4213458C69c19E6792510E1153cb0c5834665fdC",
    ]
}.get(chain.id, [])

def _unpack_results(
    vault: Address, 
    is_experiment: bool, 
    _views: List[str], 
    results: List[Any], 
    scale: int, 
    price_or_exception: Union[float, BaseException], 
    strategies: List[str], 
    strategy_descs: List[Dict],
) -> Dict[str,Any]:
    try:
        info = dict(zip(_views, results))
        for name in info:
            if name in VAULT_VIEWS_SCALED:
                info[name] /= scale
        info["strategies"] = {}
    except ValueError as e:
        info = {"strategies": {}}
 
    if isinstance(price_or_exception, BaseException):
        # Sometimes we fail to fetch price during blocks prior to the first deposit to a vault.
        # In this case (totalSupply == 0), missing price data is totally fine and we can set price = 0.
        # In all other cases, missing price data indicates an issue. We must raise and debug the Exception.
        if info["totalSupply"] > 0 and vault not in BORKED:
            logger.warning(f"The exception below is for vault: {vault}")
            raise price_or_exception
        price_or_exception = 0
    
    price = price_or_exception
    
    info["token price"] = float(price)
    if "totalAssets" in info:
        info["tvl"] = float(info["token price"]) * info["totalAssets"]

    for strategy_name, desc in zip(strategies, strategy_descs):
        info["strategies"][strategy_name] = desc

    info["experimental"] = is_experiment
    info["address"] = vault
    info["version"] = "v2"
    return info

    
class Vault:
    def __init__(self, vault: Contract, api_version=None, token=None, registry=None):
        self._strategies: Dict[Address, Strategy] = {}
        self._revoked: Dict[Address, Strategy] = {}
        self._reports = []
        self.vault: Contract = vault
        self.api_version = api_version
        if token is None:
            token = vault.token()
        try:
            self.token = Contract(token)
        except ContractNotVerified as e:
            if token not in [
                "0x08BfA22bB3e024CDfEB3eca53c0cb93bF59c4147", 
                "0x79586fa680958102154093B795Fdb8EFBc013822", 
                "0x021cF6B7ebb8c8EFcF21396Eb4c94658976172c7",
            ]:
                raise Exception(e, f"vault: {vault}")
            self.token = token
        self.registry = registry
        self.scale = 10 ** self.vault.decimals()
        # multicall-safe views with 0 inputs and numeric output.
        self._views = safe_views(self.vault.abi)
        self._calls = [[self.vault, view] for view in self._views]

        # load strategies from events and watch for freshly attached strategies
        self._events = VaultEvents(self)

    def __repr__(self):
        strategies = "..."  # don't block if we don't have the strategies loaded
        with suppress(RuntimeError): # NOTE on RuntimeError, event loop isnt running and task doesn't exist. can't be created, is not complete. no need to check strats.
            if self._task.done():
                strategies = ", ".join(map(str, self._strategies))
        return f'<Vault {self.vault} name="{self.name}" token={self.token} strategies=[{strategies}]>'

    def __hash__(self) -> int:
        return hash(self.vault.address)

    def __eq__(self, other):
        if isinstance(other, Vault):
            return self.vault == other.vault

        if isinstance(other, str):
            return self.vault == other
        
        # Needed for transactions_exporter
        if isinstance(other, Ygov):
            return False

        raise ValueError("Vault is only comparable with [Vault, str]")

    @classmethod
    def from_address(cls, address):
        vault = Contract(address)
        instance = cls(vault=vault, token=vault.token(), api_version=vault.apiVersion())
        instance.name = vault.name()
        return instance

    @async_property
    @stuck_coro_debugger
    async def strategies(self) -> List[Strategy]:
        await self.load_strategies()
        return list(self._strategies.values())
    
    async def strategies_at_block(self, block: int) -> AsyncIterator[Strategy]:
        self._task  # ensure fetcher task is running
        working = {}
        async for _ in self._events.events(to_block=block):
            for address in self._strategies:
                if address in working:
                    continue
                working[address] = asyncio.create_task(contract_creation_block_async(address, when_no_history_return_0=True))
        async for address, deploy_block in a_sync.as_completed(working, aiter=True):
            if deploy_block > block:
                continue
            while address not in self._strategies:
                logger.info('%s not in %s._strategies', address, self)
                await asyncio.sleep(5)
            yield self._strategies[address]

    @async_property
    @stuck_coro_debugger
    async def revoked_strategies(self) -> List[Strategy]:
        await self.load_strategies()
        return list(self._revoked.values())

    @async_property
    @stuck_coro_debugger
    async def reports(self):
        # strategy reports are loaded at the same time as other vault strategy events
        await self.load_strategies()
        return self._reports

    @async_property
    @stuck_coro_debugger
    async def is_endorsed(self):
        if not self.registry:
            return None
        return str(self.vault) in await self.registry.vaults

    @async_property
    @stuck_coro_debugger
    async def is_experiment(self):
        if not self.registry:
            return None
        # experimental vaults are either listed in the registry or have the 0x address suffix in the name
        return str(self.vault) in await self.registry.experiments or re.search(r"0x.*$", self.name) is not None

    @stuck_coro_debugger
    async def is_active(self, block: Optional[int]) -> bool:
        if block and await contract_creation_block_async(str(self.vault)) > block:
            return False
        # fixes edge case: a vault is not necessarily initialized on creation
        return await self.vault.activation.coroutine(block_identifier=block)

    @stuck_coro_debugger
    async def load_strategies(self):
        await self._task

    async def watch_events(self) -> NoReturn:
        start = time.time()
        await self._events.events(await dank_mids.eth.block_number)
        logger.info("loaded %d strategies %s in %.3fs", len(self._strategies), self.name, time.time() - start)

    @stuck_coro_debugger
    async def describe(self, block=None):
        block = block or await dank_mids.eth.block_number
        results, strategy_descs, price = await asyncio.gather(
            fetch_multicall_async(*self._calls, block=block),
            self._describe_strategies(block),
            get_price_return_exceptions(self.token, block=block),
        )
        return _unpack_results(
            self.vault.address,
            await self.is_experiment,
            self._views,
            results,
            self.scale,
            price,
            await asyncio.gather(*(strategy.unique_name for strategy in await self.strategies)),
            strategy_descs,
        )
        
    @stuck_coro_debugger
    async def apy(self, samples: "ApySamples"):
        from yearn import apy
        if await self._needs_curve_simple:
            return await apy.curve.simple(self, samples)
        elif pool := await apy.velo.get_staking_pool(self.token.address):
            return await apy.velo.staking(self, pool, samples)
        elif pool := await apy.aero.get_staking_pool(self.token.address):
            return await apy.aero.staking(self, pool, samples)
        elif Version(self.api_version) >= Version("0.3.2"):
            return await apy.v2.average(self, samples)
        else:
            return await apy.v2.simple(self, samples)
        
    @stuck_coro_debugger
    async def tvl(self, block=None):
        total_assets = await self.vault.totalAssets.coroutine(block_identifier=block)
        try:
            # hardcode frxETH-sfrxETH to frxETH-WETH price for now
            if self.vault.address == "0xc2626aCEdc27cFfB418680d0307C9178955A4743":
                price = await get_price("0x3f42Dc59DC4dF5cD607163bC620168f7FF7aB970", block=block, sync=False) 
            else:
                price = await get_price(self.token, block=None, sync=False)
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = 0
            
        tvl = total_assets * price / await ERC20(self.vault, asynchronous=True).scale if price else None
        return Tvl(total_assets, price, tvl)

    @cached_property
    def _task(self) -> asyncio.Task:
        """The daemon task that loads events for this vault. Starts when first accessed."""
        return asyncio.create_task(self.watch_events())
        
    @async_cached_property
    @stuck_coro_debugger
    async def _needs_curve_simple(self):
        # some curve vaults which should not be calculated with curve logic
        curve_simple_excludes = {
            Network.Arbitrum: [
                "0x1dBa7641dc69188D6086a73B972aC4bda29Ec35d", # supplies MIM3CRV-f to Abracadabra to earn SPELL
            ]
        }
        needs_simple = True
        if chain.id in curve_simple_excludes:
            needs_simple = self.vault.address not in curve_simple_excludes[chain.id]

        return needs_simple and magic.curve and await magic.curve.get_pool(self.token.address)
    
    @stuck_coro_debugger
    async def _describe_strategies(self, block: int) -> List[dict]:
        return await asyncio.gather(*[asyncio.create_task(strategy.describe(block=block)) async for strategy in self.strategies_at_block(block)])
    
    
class VaultEvents(ProcessedEvents[_EventItem]):
    __slots__ = "vault",
    def __init__(self, vault: Vault, **kwargs: Any):
        topics = [[encode_hex(event_abi_to_log_topic(event)) for event in vault.vault.abi if event["type"] == "event" and event["name"] in STRATEGY_EVENTS]]
        super().__init__(addresses=[str(vault.vault)], topics=topics, **kwargs)
        self.vault = vault
    def _process_event(self, event: _EventItem) -> _EventItem:
        # some issues during the migration of this strat prevented it from being verified so we skip it here...
        try:
            if chain.id == Network.Optimism:
                failed_migration = False
                for key in ["newVersion", "oldVersion", "strategy"]:
                    failed_migration |= (key in event and event[key] == "0x4286a40EB3092b0149ec729dc32AD01942E13C63")
                if failed_migration:
                    return event

            if event.name == "StrategyAdded":
                strategy_address = event["strategy"]
                logger.debug("%s strategy added %s", self.vault.name, strategy_address)
                try: 
                    self.vault._strategies[strategy_address] = Strategy(strategy_address, self.vault)
                except ValueError:
                    logger.error(f"Error loading strategy {strategy_address}")
            elif event.name == "StrategyRevoked":
                logger.debug("%s strategy revoked %s", self.vault.name, event["strategy"])
                self.vault._revoked[event["strategy"]] = self.vault._strategies.pop(
                    event["strategy"], Strategy(event["strategy"], self.vault)
                )
            elif event.name == "StrategyMigrated":
                logger.debug("%s strategy migrated %s -> %s", self.vault.name, event["oldVersion"], event["newVersion"])
                self.vault._revoked[event["oldVersion"]] = self.vault._strategies.pop(
                    event["oldVersion"], Strategy(event["oldVersion"], self.vault)
                )
                self.vault._strategies[event["newVersion"]] = Strategy(event["newVersion"], self.vault)
            elif event.name == "StrategyReported":
                self.vault._reports.append(event)
            return event
        except Exception as e:
            logger.exception(e)
            raise e