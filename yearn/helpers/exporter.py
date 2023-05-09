
import asyncio
import logging
import os
import time
from asyncio.queues import QueueEmpty
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from itertools import cycle
from random import randint
from typing import Awaitable, Callable, Literal, NoReturn, Optional, TypeVar, AsyncIterator

import eth_retry
from brownie import chain
from dank_mids.controller import instances
from y.datatypes import Block
from y.networks import Network
from y.time import closest_block_after_timestamp_async
from y.utils.dank_mids import dank_w3

from yearn.helpers.snapshots import (RESOLUTION, SLEEP_TIME, Resolution,
                                     _generate_snapshot_range_forward,
                                     _generate_snapshot_range_historical,
                                     _get_intervals)
from yearn.outputs.victoria.victoria import _build_item, _post, has_data
from yearn.sentry import log_task_exceptions
from yearn.utils import use_memray_if_enabled

logger = logging.getLogger(__name__)

SHOW_STATS = bool(os.environ.get("SHOW_STATS"))

_get_priority = lambda: randint(0, 500)

'''
@eth_retry.auto_retry
async def _wait_for_block(timestamp: int) -> Block:
    block = None
    while True:
        block, latest = await asyncio.gather(
            dank_w3.eth.get_block("latest" if block is None else block.number + 1 if block.number < latest.number else latest.number),
            dank_w3.eth.get_block("latest")
        )
        while timestamp >= block.timestamp and block.number < latest.number:
            # We are lagging behind chain head, likely because we are on a chain with fast block times
            block = await dank_w3.eth.get_block(block.number + 1)
            if timestamp < block.timestamp:
                logger.info(f'[0] returning {block.number - 1}')
                return block.number - 1
            logger.info(f'[0] block: {block.number}, timestamp: {block.timestamp}')

        while timestamp < block.timestamp:
            logger.info(f'[1] block: {block.number}, block.timestamp: {block.timestamp}, timestamp: {timestamp}')
            try:
                prev_block = await dank_w3.eth.get_block(block.number - 1)
                if prev_block.timestamp < timestamp:
                    logger.info(f'[1] returning {block.number}')
                    return block.number
                if block.timestamp == prev_block.timestamp:
                    # Some chains need bigger leaps due to fast block times
                    block = await dank_w3.eth.get_block(block.number - 10)
                else:
                    block = prev_block
            except ValueError as e:
                if 'parse error' not in str(e):
                    raise
        logger.info('neither')
        await asyncio.sleep(SLEEP_TIME)
'''

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
        start_block: int,
        max_concurrent_runs: int = int(os.environ.get("MAX_CONCURRENT_RUNS", 12)),
        max_concurrent_runs_per_resolution: int = int(os.environ.get("MAX_CONCURRENT_RUNS_PER_RESOLUTION", 5)),
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
        self._concurrency = max_concurrent_runs
        self._data_semaphore = asyncio.Semaphore(self._concurrency)
        self._res_semaphore = defaultdict(lambda: asyncio.Semaphore(max_concurrent_runs_per_resolution))
        self._has_data_semaphore = asyncio.Semaphore(2)
        self._export_semaphore = asyncio.Semaphore(5)
        
        self._snapshots_fetched = 0
        self._snapshots_exported = 0
    
    def run(self, direction: Optional[Direction] = None) -> NoReturn:
        use_memray_if_enabled(self.name)(self._run)(direction)

    def _run(self, direction: Optional[Direction] = None) -> NoReturn:
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
        """ Exports all historical and future data. This coroutine will run forever. """
        await asyncio.gather(self.export_history(), self.export_future())
    
    async def export_future(self) -> NoReturn:
        """ Exports all future data. This coroutine will run forever. """
        start = datetime.now(tz=timezone.utc)
        intervals = _get_intervals(start)
        start = intervals[RESOLUTION]['start'] 
        interval = intervals[RESOLUTION]['interval']
        # Bump forward to the next snapshot, as the historical coroutine will take care of this one.
        start = start + interval
        loop = self.loop
        async def task(snapshot: datetime) -> None:
            block = await closest_block_after_timestamp_async(snapshot, wait_for_block_if_needed=True)
            await self.export_snapshot(block, snapshot)
        async for snapshot in _generate_snapshot_range_forward(start, interval):
            loop.create_task(task(snapshot))
    
    async def export_history(self) -> None:
        """ Exports all historical data. This coroutine runs for a finite duration. """
        logger.info(f"exporting {Network.name()} {self.name} snapshots for resolution {RESOLUTION}")
        start = datetime.now(tz=timezone.utc)
        intervals = _get_intervals(start)
        loop = self.loop
        
        work_items = [
            WorkItem(snapshot, resolution)
            for resolution in intervals
            async for snapshot in _generate_snapshot_range_historical(self.start_timestamp, resolution, intervals)
        ]
        
        # Use Queue to conserve memory instead of creating all futures at once
        queues = defaultdict(asyncio.PriorityQueue)
        for work_item in work_items:
            queue_item = _get_priority(), work_item
            queues[work_item.resolution].put_nowait(queue_item)
        queues = queues.values()
        c_queues = cycle(queues)
        
        running_futs = []

        def prune_completed_futs() -> None:
            fut: asyncio.Future
            for fut in running_futs[:]:
                if fut.done():
                    if e := fut.exception():
                        logger.warning(e, exc_info=True)
                    running_futs.pop(running_futs.index(fut))
                    
        async def futures() -> AsyncIterator[asyncio.Future]:
            work_item: WorkItem
            max_running_futs = self._concurrency * 10  # Some arbitrary number
            while not all(queue.empty() for queue in queues):
                prune_completed_futs()
                await asyncio.sleep(0.001)
                if len(running_futs) >= max_running_futs:
                    continue
                queue = next(c_queues)
                try:
                    _, work_item = queue.get_nowait()
                    logger.info(f'starting fut for {work_item.resolution} {work_item.snapshot}. {queue.qsize()} remain.')
                    yield asyncio.ensure_future(
                        self.export_historical_snapshot_if_missing(work_item.snapshot, work_item.resolution),
                        loop=loop,
                    )
                except QueueEmpty:
                    logger.debug(queue)
        
        async for fut in futures():
            running_futs.append(fut)
            
        while running_futs:
            prune_completed_futs()
            await asyncio.sleep(10)
        logger.info(f'{Network.name()} {self.name} historical export completed')
    
    # Export Methods
    
    @log_task_exceptions
    async def export_snapshot(self, block: int, snapshot: datetime, resolution: Optional[Resolution] = None) -> None:
        # Fetch data
        async with self._res_semaphore[resolution]:
            async with self._data_semaphore:
                start = time.time()
                ts = snapshot.timestamp()
                data = await self._data_fn(block, ts)
                duration = time.time() - start
                self._snapshots_fetched += 1

        # Process stats
        if SHOW_STATS:
            snapshots = self._snapshots_fetched
            requests = instances[0].worker.request_uid.latest
            logger.info(f"exported {snapshots} snapshots in {requests} requests")
            logger.info(f"Avg rate of {round(requests/snapshots, 2)} requests per snapshot. Currently only considers eth_calls.")
        
        # Export to datastore
        await self._export_data(data)
        logger.info(f"exported {Network.name()} {self.name} snapshot %s block=%d took=%.3fs", snapshot, block, duration)
        await self._export_duration(duration, ts)
    
    @log_task_exceptions
    async def export_historical_snapshot_if_missing(self, snapshot: datetime, resolution: Resolution) -> None:
        if not await self._has_data(snapshot):
            timestamp = int(snapshot.timestamp())
            block = await closest_block_after_timestamp_async(timestamp)
            await self.export_snapshot(block, snapshot, resolution)
    
    # Datastore Methods

    async def _has_data(self, snapshot: datetime) -> bool:
        ts = snapshot.timestamp()
        async with self._has_data_semaphore:
            response = await has_data(ts, self.data_query)
        if response:
            logger.info(f"data already present for {Network.name()} {self.name} snapshot {snapshot}, ts {ts}")
        return bool(response)

    async def _export_data(self, data: T) -> None:
        async with self._export_semaphore:
            await self._export_fn(data)
        self._snapshots_exported += 1
    
    async def _export_duration(self, duration_seconds: float, timestamp_seconds: float) -> None:
        async with self._export_semaphore:
            item = _build_item(
                "export_duration",
                [ "concurrency", "exporter" ],
                [ self._concurrency, self.name ],
                duration_seconds,
                timestamp_seconds
                )
            await _post([item])
    
