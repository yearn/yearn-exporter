import asyncio
import logging
import re
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List, Union

from async_property import async_cached_property
from brownie import chain
from eth_utils import encode_hex, event_abi_to_log_topic
from joblib import Parallel, delayed
from multicall.utils import run_in_subprocess
from semantic_version.base import Version
from y import ERC20, Contract, Network, magic
from y.exceptions import NodeNotSynced, PriceError, yPriceMagicError
from y.networks import Network
from y.prices import magic
from y.utils.events import get_logs_asap

from yearn.common import Tvl
from yearn.decorators import sentry_catch_all, wait_or_exit_after
from yearn.events import decode_logs, get_logs_asap
from yearn.multicall2 import fetch_multicall_async
from yearn.special import Ygov
from yearn.typing import Address
from yearn.utils import run_in_thread, safe_views
from yearn.v2.strategies import Strategy

if TYPE_CHECKING:
    from yearn.apy.common import ApySamples

VAULT_VIEWS_SCALED = [
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
]

# we are only interested in strategy-related events
STRATEGY_EVENTS = [
    "StrategyAdded",
    "StrategyMigrated",
    "StrategyRevoked",
    "StrategyReported",
]

logger = logging.getLogger(__name__)

async def get_price_return_exceptions(token, block=None):
    try:
        return await magic.get_price(token, block=block, silent=True, sync=False)
    except Exception as e:
        return e

BORKED = {
    Network.Mainnet: [
        # borked in the vyper exploit of july 2023
        "0x718AbE90777F5B778B52D553a5aBaa148DD0dc5D",
    ]
}.get(chain.id, [])

def _unpack_results(vault: Address, is_experiment: bool, _views: List[str], results: List[Any], scale: int, price_or_exception: Union[float, BaseException], strategies: List[str], strategy_descs: List[Dict]) -> Dict[str,Any]:
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
        info["tvl"] = info["token price"] * info["totalAssets"]

    for strategy_name, desc in zip(strategies, strategy_descs):
        info["strategies"][strategy_name] = desc

    info["experimental"] = is_experiment
    info["address"] = vault
    info["version"] = "v2"
    return info


class Vault:
    def __init__(self, vault: Contract, api_version=None, token=None, registry=None, watch_events_forever=True):
        self._strategies: Dict[Address, Strategy] = {}
        self._revoked: Dict[Address, Strategy] = {}
        self._reports = []
        self.vault: Contract = vault
        self.api_version = api_version
        if token is None:
            token = vault.token()
        self.token = Contract(token)
        self.registry = registry
        self.scale = 10 ** self.vault.decimals()
        # multicall-safe views with 0 inputs and numeric output.
        self._views = safe_views(self.vault.abi)

        # load strategies from events and watch for freshly attached strategies
        self._topics = [
            [
                encode_hex(event_abi_to_log_topic(event))
                for event in self.vault.abi
                if event["type"] == "event" and event["name"] in STRATEGY_EVENTS
            ]
        ]
        self._watch_events_forever = watch_events_forever
        self._done = threading.Event()
        self._has_exception = False
        self._thread = threading.Thread(target=self.watch_events, daemon=True)

    def __repr__(self):
        strategies = "..."  # don't block if we don't have the strategies loaded
        if self._done.is_set():
            strategies = ", ".join(f"{strategy}" for strategy in self.strategies)
        return f'<Vault {self.vault} name="{self.name}" token={self.token} strategies=[{strategies}]>'

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

    @property
    def strategies(self) -> List[Strategy]:
        self.load_strategies()
        return list(self._strategies.values())

    @property
    def revoked_strategies(self) -> List[Strategy]:
        self.load_strategies()
        return list(self._revoked.values())

    @property
    def reports(self):
        # strategy reports are loaded at the same time as other vault strategy events
        self.load_strategies()
        return self._reports

    @property
    def is_endorsed(self):
        if not self.registry:
            return None
        return str(self.vault) in self.registry.vaults

    @property
    def is_experiment(self):
        if not self.registry:
            return None
        # experimental vaults are either listed in the registry or have the 0x address suffix in the name
        return str(self.vault) in self.registry.experiments or re.search(r"0x.*$", self.name) is not None

    @wait_or_exit_after
    def load_strategies(self):
        if not self._thread._started.is_set():
            self._thread.start()

    def load_harvests(self):
        Parallel(1, "threading")(delayed(strategy.load_harvests)() for strategy in self.strategies)

    @sentry_catch_all
    def watch_events(self):
        start = time.time()
        sleep_time = 300
        from_block = None
        height = chain.height
        while True:
            logs = get_logs_asap(str(self.vault), topics=self._topics, from_block=from_block, to_block=height)
            events = decode_logs(logs)
            self.process_events(events)
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded %d strategies %s in %.3fs", len(self._strategies), self.name, time.time() - start)
            if not self._watch_events_forever:
                return
            time.sleep(sleep_time)

            # set vars for next loop
            from_block = height + 1
            height = chain.height
            if height < from_block:
                raise NodeNotSynced(f"No new blocks in the past {sleep_time/60} minutes.")


    def process_events(self, events):
        for event in events:
            # some issues during the migration of this strat prevented it from being verified so we skip it here...
            if chain.id == Network.Optimism:
                failed_migration = False
                for key in ["newVersion", "oldVersion", "strategy"]:
                    failed_migration |= (key in event and event[key] == "0x4286a40EB3092b0149ec729dc32AD01942E13C63")
                if failed_migration:
                    continue

            if event.name == "StrategyAdded":
                strategy_address = event["strategy"]
                logger.debug("%s strategy added %s", self.name, strategy_address)
                try: 
                    self._strategies[strategy_address] = Strategy(strategy_address, self, self._watch_events_forever)
                except ValueError:
                    logger.error(f"Error loading strategy {strategy_address}")
                    pass
            elif event.name == "StrategyRevoked":
                logger.debug("%s strategy revoked %s", self.name, event["strategy"])
                self._revoked[event["strategy"]] = self._strategies.pop(
                    event["strategy"], Strategy(event["strategy"], self, self._watch_events_forever)
                )
            elif event.name == "StrategyMigrated":
                logger.debug("%s strategy migrated %s -> %s", self.name, event["oldVersion"], event["newVersion"])
                self._revoked[event["oldVersion"]] = self._strategies.pop(
                    event["oldVersion"], Strategy(event["oldVersion"], self, self._watch_events_forever)
                )
                self._strategies[event["newVersion"]] = Strategy(event["newVersion"], self, self._watch_events_forever)
            elif event.name == "StrategyReported":
                self._reports.append(event)

    async def _unpack_results(self, results):
        results, strategy_descs, price = results
        strategies = await run_in_thread(getattr, self, 'strategies')
        return await run_in_subprocess(
            _unpack_results,
            self.vault.address,
            self.is_experiment,
            self._views,
            results,
            self.scale,
            price,
            # must be picklable.
            [strategy.unique_name for strategy in strategies],
            strategy_descs,
        )

    async def describe(self, block=None):
        strategies = await run_in_thread(getattr, self, 'strategies')
        results = await asyncio.gather(
            fetch_multicall_async(*[[self.vault, view] for view in self._views], block=block),
            asyncio.gather(*[strategy.describe(block=block) for strategy in strategies]),
            get_price_return_exceptions(self.token, block=block)
        )
        return await self._unpack_results(results)

    async def apy(self, samples: "ApySamples"):
        from yearn import apy
        if self._needs_curve_simple:
            return await apy.curve.simple(self, samples)
        elif pool := await apy.velo.get_staking_pool(self.token.address):
            return await apy.velo.staking(self, pool, samples)
        elif pool := await apy.aero.get_staking_pool(self.token.address):
            return await apy.aero.staking(self, pool, samples)
        elif Version(self.api_version) >= Version("0.3.2"):
            return await apy.v2.average(self, samples)
        else:
            return await apy.v2.simple(self, samples)
        
    async def tvl(self, block=None):
        total_assets = await self.vault.totalAssets.coroutine(block_identifier=block)
        try:
            # hardcode frxETH-sfrxETH to frxETH-WETH price for now
            if self.vault.address == "0xc2626aCEdc27cFfB418680d0307C9178955A4743":
                price = await magic.get_price("0x3f42Dc59DC4dF5cD607163bC620168f7FF7aB970", block=block, sync=False) 
            else:
                price = await magic.get_price(self.token, block=None, sync=False)
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = 0
            
        tvl = total_assets * price / await ERC20(self.vault, asynchronous=True).scale if price else None
        return Tvl(total_assets, price, tvl)

    @async_cached_property
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
