import logging
from functools import cached_property
from itertools import chain
from typing import AsyncIterator

from async_property import async_property
from brownie.network.event import _EventItem
from eth_utils import encode_hex, event_abi_to_log_topic
from web3.exceptions import ContractLogicError
from y import Contract
from y._decorators import stuck_coro_debugger
from y.utils.events import ProcessedEvents

from yearn.multicall2 import fetch_multicall_async
from yearn.utils import safe_views

STRATEGY_VIEWS_SCALED = {
    "maxDebtPerHarvest",
    "minDebtPerHarvest",
    "totalDebt",
    "totalGain",
    "totalLoss",
    "estimatedTotalAssets",
    "lentTotalAssets",
    "balanceOfPool",
    "balanceOfWant",
}

STRATEGY_EVENTS = ["Harvested"]

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(self, strategy, vault):
        self.strategy = Contract(strategy)
        self.vault = vault
        try:
            self.name = self.strategy.name()
        except (ValueError, ContractLogicError):
            self.name = strategy[:10]
        self._views = safe_views(self.strategy.abi)
        self._events = Harvests(self)

    @async_property
    async def unique_name(self):
        if [strategy.name for strategy in await self.vault.strategies].count(self.name) > 1:
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

    async def harvests(self, thru_block: int) -> AsyncIterator[dict]:
        async for event in self._events.events(to_block=thru_block):
            yield event
    
    @stuck_coro_debugger
    async def describe(self, block=None):
        results = await fetch_multicall_async(*self._calls, block=block)
        
        # unpack self.vault.vault.strategies(self.strategy)
        results = chain(zip(self._views, results), results[-1].dict().items())
        
        scale = self.vault.scale
        return {
            view: (
                # scale views
                (result or 0) / scale if view in STRATEGY_VIEWS_SCALED else 
                # unwrap structs
                result.dict() if hasattr(result, '_dict') else 
                result
            ) 
            for view, result in results
        }

    @cached_property
    def _calls(self):
        return *[[self.strategy, view] for view in self._views], [self.vault.vault, "strategies", self.strategy],


class Harvests(ProcessedEvents[int]):
    def __init__(self, strategy: Strategy):
        topics = [
            [
                encode_hex(event_abi_to_log_topic(event))
                for event in strategy.strategy.abi
                if event["type"] == "event" and event["name"] in STRATEGY_EVENTS
            ]
        ]
        super().__init__(addresses=[str(strategy.strategy)], topics=topics)
        self.strategy = strategy
    def _include_event(self, event: _EventItem) -> bool:
        return event.name == "Harvested"
    def _get_block_for_obj(self, block: int) -> int:
        return block
    # TODO: work this in somehow:
    #   logger.info("loaded %d harvests %s in %.3fs", len(self._harvests), self.name, time.time() - start)
    def _process_event(self, event: _EventItem) -> int:
        block = event.block_number
        logger.debug("%s harvested on %d", self.strategy.name, block)
        return block
