import logging
import re
import threading
import time
from typing import List

from brownie import chain
from eth_utils import encode_hex, event_abi_to_log_topic
from joblib import Parallel, delayed
from semantic_version.base import Version
from yearn import apy
from yearn.apy.common import ApySamples
from yearn.common import Tvl
from yearn.events import create_filter, decode_logs
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.prices.curve import curve
from yearn.utils import safe_views, contract
from yearn.v2.strategies import Strategy
from yearn.exceptions import PriceError
from yearn.decorators import sentry_catch_all, wait_or_exit_after

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


class Vault:
    def __init__(self, vault, api_version=None, token=None, registry=None, watch_events_forever=True):
        self._strategies = {}
        self._revoked = {}
        self._reports = []
        self.vault = vault
        self.api_version = api_version
        if token is None:
            token = vault.token()
        self.token = contract(token)
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

        raise ValueError("Vault is only comparable with [Vault, str]")

    @classmethod
    def from_address(cls, address):
        vault = contract(address)
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
        Parallel(8, "threading")(delayed(strategy.load_harvests)() for strategy in self.strategies)

    @sentry_catch_all
    def watch_events(self):
        start = time.time()
        self.log_filter = create_filter(str(self.vault), topics=self._topics)
        while True:
            logs = self.log_filter.get_new_entries()
            events = decode_logs(logs)
            self.process_events(events)
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded %d strategies %s in %.3fs", len(self._strategies), self.name, time.time() - start)
            if not self._watch_events_forever:
                return
            time.sleep(300)

    def process_events(self, events):
        for event in events:
            if event.name == "StrategyAdded":
                strategy_address = event["strategy"]
                logger.debug("%s strategy added %s", self.name, strategy_address)
                try: 
                    self._strategies[strategy_address] = Strategy(strategy_address, self, self._watch_events_forever)
                except ValueError:
                    print(f"Error loading strategy {strategy_address}")
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

    def describe(self, block=None):
        try:
            results = fetch_multicall(*[[self.vault, view] for view in self._views], block=block)
            info = dict(zip(self._views, results))
            for name in info:
                if name in VAULT_VIEWS_SCALED:
                    info[name] /= self.scale
            info["strategies"] = {}
        except ValueError as e:
            info = {"strategies": {}}

        for strategy in self.strategies:
            info["strategies"][strategy.unique_name] = strategy.describe(block=block)

        info["token price"] = magic.get_price(self.token, block=block)
        if "totalAssets" in info:
            info["tvl"] = info["token price"] * info["totalAssets"]

        info["experimental"] = self.is_experiment
        info["address"] = self.vault
        info["version"] = "v2"
        
        return info

    def apy(self, samples: ApySamples):
        if curve and curve.get_pool(self.token.address):
            return apy.curve.simple(self, samples)
        elif Version(self.api_version) >= Version("0.3.2"):
            return apy.v2.average(self, samples)
        else:
            return apy.v2.simple(self, samples)

    def tvl(self, block=None):
        total_assets = self.vault.totalAssets(block_identifier=block)
        try:
            price = magic.get_price(self.token, block=None)
        except PriceError:
            price = None
        tvl = total_assets * price / 10 ** self.vault.decimals(block_identifier=block) if price else None
        return Tvl(total_assets, price, tvl)