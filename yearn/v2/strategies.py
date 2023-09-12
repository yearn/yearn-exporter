import logging
import threading
import time
from functools import cached_property
from typing import Any, List

from brownie import chain
from eth_utils import encode_hex, event_abi_to_log_topic
from multicall.utils import run_in_subprocess
from y.exceptions import NodeNotSynced

from yearn.decorators import sentry_catch_all, wait_or_exit_after
from yearn.events import decode_logs, get_logs_asap
from yearn.multicall2 import fetch_multicall_async
from yearn.utils import contract, safe_views

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

def _unpack_results(views: List[str], results: List[Any], scale: int):
    # unpack self.vault.vault.strategies(self.strategy)
    info = dict(zip(views, results))
    info.update(results[-1].dict())
    # scale views
    for view in STRATEGY_VIEWS_SCALED:
        if view in info:
            info[view] = (info[view] or 0) / scale
    # unwrap structs
    for view in info:
        if hasattr(info[view], '_dict'):
            info[view] = info[view].dict()
    return info


class Strategy:
    def __init__(self, strategy, vault, watch_events_forever):
        self.strategy = contract(strategy)
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
        self._has_exception = False
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

    @sentry_catch_all
    def watch_events(self):
        start = time.time()
        sleep_time = 300
        from_block = None
        height = chain.height
        while True:
            logs = get_logs_asap(str(self.strategy), topics=self._topics, from_block=from_block, to_block=height)
            events = decode_logs(logs)
            self.process_events(events)
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded %d harvests %s in %.3fs", len(self._harvests), self.name, time.time() - start)
            if not self._watch_events_forever:
                return
            time.sleep(sleep_time)

            # read new logs at end of loop
            from_block = height + 1
            height = chain.height
            if height < from_block:
                raise NodeNotSynced(f"No new blocks in the past {sleep_time/60} minutes.")


    def process_events(self, events):
        for event in events:
            if event.name == "Harvested":
                block = event.block_number
                logger.debug("%s harvested on %d", self.name, block)
                self._harvests.append(block)

    @wait_or_exit_after
    def load_harvests(self):
        if not self._thread._started.is_set():
            self._thread.start()

    @property
    def harvests(self) -> List[int]:
        self.load_harvests()
        return self._harvests
    
    @cached_property
    def _calls(self):
        return *[[self.strategy, view] for view in self._views], [self.vault.vault, "strategies", self.strategy],
    
    async def _unpack_results(self, results):
        return await run_in_subprocess(_unpack_results, self._views, results, self.vault.scale)
    
    async def describe(self, block=None):
        results = await fetch_multicall_async(*self._calls, block=block)
        return await self._unpack_results(results)
