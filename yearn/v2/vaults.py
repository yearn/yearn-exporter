import logging
import threading
import time
from typing import List

from brownie import Contract, chain
from eth_utils import encode_hex, event_abi_to_log_topic
from yearn.events import create_filter, decode_logs
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.utils import safe_views
from yearn.v2.strategies import Strategy

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
    # "StrategyReported",
]

logger = logging.getLogger(__name__)


class Vault:
    def __init__(self, vault, api_version=None, token=None, registry=None):
        self._strategies = {}
        self._revoked = {}
        self.vault = vault
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
        self._done = threading.Event()
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
        assert self.registry, "Vault not from Registry"
        return str(self.vault) in self.registry.vaults

    @property
    def is_experiment(self):
        assert self.registry, "Vault not from Registry"
        return str(self.vault) in self.registry.experiments

    def load_strategies(self):
        if not self._thread._started.is_set():
            self._thread.start()
        self._done.wait()

    def watch_events(self):
        start = time.time()
        self.log_filter = create_filter(str(self.vault), topics=self._topics)
        for block in chain.new_blocks():
            logs = self.log_filter.get_new_entries()
            events = decode_logs(logs)
            self.process_events(events)
            if not self._done.is_set():
                self._done.set()
                logger.debug("loaded %d strategies in %.3fs", len(self._strategies), self.name, time.time() - start)
            time.sleep(300)

    def process_events(self, events):
        for event in events:
            if event.name == "StrategyAdded":
                logger.debug("%s strategy added %s", self.name, event["strategy"])
                self._strategies[event["strategy"]] = Strategy(event["strategy"], self)
            elif event.name == "StrategyRevoked":
                logger.debug("%s strategy revoked %s", self.name, event["strategy"])
                self._revoked[event["strategy"]] = self._strategies.pop(
                    event["strategy"], Strategy(event["strategy"], self)
                )
            elif event.name == "StrategyMigrated":
                logger.debug("%s strategy migrated %s -> %s", self.name, event["oldVersion"], event["newVersion"])
                self._revoked[event["oldVersion"]] = self._strategies.pop(
                    event["oldVersion"], Strategy(event["oldVersion"], self)
                )
                self._strategies[event["newVersion"]] = Strategy(event["newVersion"], self)

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
            info["strategies"][strategy.name] = strategy.describe(block=block)

        info["token price"] = magic.get_price(self.token, block=block)
        if "totalAssets" in info:
            info["tvl"] = info["token price"] * info["totalAssets"]

        return info
