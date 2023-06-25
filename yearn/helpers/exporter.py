import asyncio
import logging
import os
import time
from asyncio.queues import QueueEmpty
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from itertools import cycle
from random import randint
from typing import (AsyncIterator, Awaitable, Callable, Literal, NoReturn,
                    Optional, TypeVar)

import eth_retry
from brownie import chain
from dank_mids.controller import instances
from y.networks import Network
from y.time import closest_block_after_timestamp_async

from yearn import constants
from yearn.helpers.snapshots import (RESOLUTION, Resolution,
                                     _generate_snapshot_range_forward,
                                     _generate_snapshot_range_historical,
                                     _get_intervals)
from yearn.outputs.victoria.victoria import _build_item, _post, has_data
from yearn.sentry import log_task_exceptions

logger = logging.getLogger(__name__)

SHOW_STATS = bool(os.environ.get("SHOW_STATS"))

_get_priority = lambda: randint(0, 500) if constants.RANDOMIZE_EXPORTS else 0

T = TypeVar('T')
Direction = Literal["forward", "historical"]

@dataclass
class WorkItem:
    snapshot: datetime
    resolution: Resolution
    
    def __lt__(self, other):
        return self.snapshot < other.snapshot if isinstance(other, WorkItem) else NotImplemented
    
class Exporter:
    """ Currently can only be used to output to victoria metrics. Can be extended for other data sources. """

    def __init__(
        self,
        name: str,
        data_query: str,
        data_fn: Callable[[int, int], Awaitable[T]], 
        export_fn: Callable[[T], Awaitable[None]],
        start_block: int
    ) -> None:
        """
        Required Args:
            - `name`: A label for the exporter
            - `data_query`: The query that is used to see if there is already data in the datasource
            - `data_fn`: 
                - A coroutine function (defined with `async def`) that will fetch the data from node.
                - Args:
                    - block_number: int
                    - timestamp: int
                - Returns: 
                    - `data` This return value will be passed into `export_fn`. Can be any type that is suitable for your `export_fn`. 
            - `export_fn`:
                - A coroutine function (defined with `async def`) that will export the `data` from `data_fn` to the datasource.
                - Args: 
                    - `data`: The return value from `data_fn`. Can any type that works for your needs. 
                - Returns: 
                    - `None`
            - `start_block`: The block number that the exporter starts at
        """

        self.name = name
        self.data_query = data_query
        self.start_block = start_block
        self.start_timestamp = datetime.fromtimestamp(chain[start_block].timestamp, tz=timezone.utc)

        self._data_fn = data_fn
        self._export_fn = eth_retry.auto_retry(export_fn)
        self._snapshots_fetched = 0
        self._snapshots_exported = 0
    
    def run(self, direction: Optional[Direction] = None) -> NoReturn:
        # smol workaround to init ypm before we dive into more async code
        # keep here so all other things are blocked until ypm has booted
        self.loop.run_until_complete(self.export_now())

        if direction is None:
            self.loop.run_until_complete(self.export_full())
        elif direction == "forward":
            self.loop.run_until_complete(self.export_future())
        elif direction == "historical":
            self.loop.run_until_complete(self.export_history())
        else:
            raise NotImplementedError(f'`direction` must be one of either `None`, `"forward"`, or `"historical"`. You passed {direction}')
    
    @cached_property
    def loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_event_loop()

    # Export Sequences

    async def export_full(self) -> NoReturn:
        """ Exports all present, historical and future data. This coroutine will run forever. """
        # the history and future exports are run concurrently
        await asyncio.gather(self.export_history(), self.export_future())

    async def export_now(self) -> NoReturn:
        """ Exports the present data. This coroutine will terminate. """
        await self.export_snapshot(datetime.now(tz=timezone.utc))

    async def export_future(self) -> NoReturn:
        """ Exports all future data. This coroutine will run forever. """
        start = datetime.now(tz=timezone.utc)
        intervals = _get_intervals(start)
        start = intervals[RESOLUTION]['start'] 
        interval = intervals[RESOLUTION]['interval']
        # Bump forward to the next snapshot, as the historical coroutine will take care of this one.
        start = start + interval
        async for snapshot in _generate_snapshot_range_forward(start, interval):
            await self.export_snapshot(snapshot)

    async def export_history(self) -> None:
        """ Exports all historical data. This coroutine runs for a finite duration. """
        start = datetime.now(tz=timezone.utc)
        intervals = _get_intervals(start)
        snapshots = [
            snapshot for resolution in intervals
            async for snapshot in _generate_snapshot_range_historical(self.start_timestamp, resolution, intervals)
        ]
        await self._enqueue("historical", snapshots)

    @log_task_exceptions
    async def export_snapshot(self, snapshot: datetime, resolution: Optional[Resolution] = None) -> None:
        # Fetch data
        await self._enqueue("snapshot", [snapshot])

    @log_task_exceptions
    async def export_historical_snapshot_if_missing(self, snapshot: datetime, resolution: Resolution) -> None:
        logger.warn("export_historical_snapshot_if_missing() is deprecated, please use the data producers")
        if not await self._has_data(snapshot):
            timestamp = int(snapshot.timestamp())
            await self.export_snapshot(snapshot, resolution)

    # Datastore Methods

    async def _has_data(self, snapshot: datetime) -> bool:
        ts = snapshot.timestamp()
        response = await has_data(ts, self.data_query)
        if response:
            logger.info(f"data already present for {Network.name()} {self.name} snapshot {snapshot}, ts {ts}")
        return bool(response)

    async def _export_data(self, data: T) -> None:
        await self._export_fn(data)
        self._snapshots_exported += 1
    
    async def _export_duration(self, duration_seconds: float, timestamp_seconds: float) -> None:
        item = _build_item(
            "export_duration",
            [ "exporter" ],
            [ self.name ],
            duration_seconds,
            timestamp_seconds
            )
        await _post([item])

    # Producer <-> Consumer methods
    async def _enqueue(self, name, snapshots, queue_size=1, num_consumers=1):
        queue = asyncio.Queue(queue_size)
        producer = asyncio.create_task(self._producer(name, queue, snapshots))
        consumers = [asyncio.create_task(self._consumer(name, queue, i)) for i in range(num_consumers)]
        await asyncio.gather(producer, *consumers)

    @log_task_exceptions
    async def _producer(self, name, queue, snapshots) -> None:
        logger.debug(f"{name} producer running")
        for snapshot in snapshots:
            try:
                if name == "historical" and await self._has_data(snapshot):
                    continue
                start = time.time()
                timestamp = int(snapshot.timestamp())
                block = await closest_block_after_timestamp_async(timestamp, wait_for_block_if_needed=True)
                data = await self._data_fn(block, timestamp)
                duration = time.time() - start
                logger.info(f"exported {Network.name()} {self.name} snapshot %s block=%d took=%.3fs", snapshot, block, duration)
                await queue.put((snapshot, data, duration, block))
                logger.debug(f"{name} produced snapshot data for {snapshot} on queue")
                self._record_stats()
            except Exception as e:
                logger.error(e, exc_info=True)

        logger.debug(f"{name} producer done")

    @log_task_exceptions
    async def _consumer(self, name: str, queue: asyncio.Queue, i: int) -> NoReturn:
        logger.debug(f"{name} consumer {i} running")
        while True:
            try:
                snapshot, data, duration, block = await queue.get()
                logger.debug(f"{name} consumer {i} got item ({snapshot})")
                await self._export_data(data)
                logger.debug(f"{name} consumer {i} is done with item ({snapshot})")
                queue.task_done()
                await self._export_duration(duration, snapshot.timestamp())
            except Exception as e:
                logger.error(e, exc_info=True)

    def _record_stats(self) -> None:
        self._snapshots_fetched += 1

        # Process stats
        if SHOW_STATS:
            snapshots = self._snapshots_fetched
            requests = instances[0].worker.request_uid.latest
            logger.info(f"exported {snapshots} snapshots in {requests} requests")
            logger.info(f"Avg rate of {round(requests/snapshots, 2)} requests per snapshot. Currently only considers eth_calls.")
