import logging
import threading
import time
from typing import List

from brownie import Contract, chain
from eth_utils import encode_hex, event_abi_to_log_topic

from yearn.utils import safe_views
from yearn.multicall2 import fetch_multicall
from yearn.events import create_filter, decode_logs


STRATEGY_VIEWS_SCALED = [
    "maxDebtPerHarvest",
    "minDebtPerHarvest",
    "totalDebt",
    "totalGain",
    "totalLoss",
    "estimatedTotalAssets",
    "lentTotalAssets",
    "balanceOfPool",
    "balanceOfWant",
]

STRATEGY_EVENTS = ["Harvested"]

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(self, strategy, vault, watch_events_forever):
        self.strategy = Contract(strategy)
        self.vault = vault
        try:
            self.name = self.strategy.name()
        except ValueError:
            self.name = strategy[:10]
        self._views = safe_views(self.strategy.abi)
        self._harvests = []
        self._topics = [
            [
                encode_hex(event_abi_to_log_topic(event))
                for event in self.strategy.abi
                if event["type"] == "event" and event["name"] in STRATEGY_EVENTS
            ]
        ]
        self._watch_events_forever = watch_events_forever
        self._done = threading.Event()
        self._thread = threading.Thread(target=self.watch_events, daemon=True)

    @property
    def unique_name(self):
        if [strategy.name for strategy in self.vault.strategies].count(self.name) > 1:
            return f'{self.name} {str(self.strategy)[:8]}'
        else:
            return self.name

    def __repr__(self) -> str:
        return f"<Strategy {self.strategy} name={self.name}>"

    def __eq__(self, other):
        if isinstance(other, Strategy):
            return self.strategy == other.strategy

        if isinstance(other, str):
            return self.strategy == other

        raise ValueError("Strategy is only comparable with [Strategy, str]")

    def watch_events(self):
        start = time.time()
        self.log_filter = create_filter(str(self.strategy), topics=self._topics)
        for block in chain.new_blocks(height_buffer=12):
            logs = self.log_filter.get_new_entries()
            events = decode_logs(logs)
            self.process_events(events)
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded %d harvests %s in %.3fs", len(self._harvests), self.name, time.time() - start)
            if not self._watch_events_forever:
                break
            time.sleep(300)

    def process_events(self, events):
        for event in events:
            if event.name == "Harvested":
                block = event.block_number
                logger.debug("%s harvested on %d", self.name, block)
                self._harvests.append(block)

    def load_harvests(self):
        if not self._thread._started.is_set():
            self._thread.start()
        self._done.wait()

    @property
    def harvests(self) -> List[int]:
        self.load_harvests()
        return self._harvests

    def describe(self, block=None):
        results = fetch_multicall(
            *[[self.strategy, view] for view in self._views],
            [self.vault.vault, "strategies", self.strategy],
            block=block,
        )
        info = dict(zip(self._views, results))
        info.update(results[-1].dict())
        for view in STRATEGY_VIEWS_SCALED:
            if view in info:
                info[view] = (info[view] or 0) / self.vault.scale
        # unwrap structs
        for view in info:
            if hasattr(info[view], '_dict'):
                info[view] = info[view].dict()

        return info
