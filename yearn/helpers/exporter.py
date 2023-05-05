
import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import cached_property
from typing import Awaitable, Callable, Literal, NoReturn, Optional, TypeVar

import eth_retry
from brownie import chain
from dank_mids.controller import instances
from eth_portfolio.constants import sync_threads
from y.datatypes import Block
from y.time import closest_block_after_timestamp
from y.utils.dank_mids import dank_w3
from yearn.helpers.snapshots import (RESOLUTION, SLEEP_TIME, Resolution,
                                     _generate_snapshot_range_forward,
                                     _generate_snapshot_range_historical,
                                     _get_intervals)
from yearn.outputs.victoria.victoria import _build_item, _post, has_data
from yearn.utils import run_in_thread

logger = logging.getLogger(__name__)

SHOW_STATS = bool(os.environ.get("SHOW_STATS"))

@eth_retry.auto_retry
async def _wait_for_block(timestamp: int) -> Block:
    while True:
        block = await dank_w3.eth.get_block("latest")
        while timestamp < block.timestamp:
            try:
                prev_block = await dank_w3.eth.get_block(block.number - 1)
                if prev_block.timestamp < timestamp:
                    return block.number
                block = prev_block
            except ValueError as e:
                if 'parse error' not in str(e):
                    raise
        await asyncio.sleep(SLEEP_TIME)

T = TypeVar('T')
Direction = Literal["forward", "historical"]

class Exporter:
    """ Currently can only be used to output to victoria metrics. Can be extended for other data sources. """
    
    def __init__(
        self,
        name: str,
        data_query: str,
        data_fn: Callable[[int, int], Awaitable[T]], 
        export_fn: Callable[[T], Awaitable[None]],
        start_block: int,
        max_concurrent_runs: int = 10,
        max_concurrent_runs_per_resolution: int = 5
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
        self._export_semaphore = asyncio.Semaphore(1)

        self._snapshots_fetched = 0
        self._snapshots_exported = 0
    
    def run(self, direction: Optional[Direction] = None) -> NoReturn:
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
        async for snapshot in _generate_snapshot_range_forward(start, interval):
            block = await _wait_for_block(snapshot.timestamp())
            loop.create_task(self.export_snapshot(block, snapshot))
    
    async def export_history(self) -> None:
        """ Exports all historical data. This coroutine runs for a finite duration. """
        logger.info(f"exporting {self.name} snapshots for resolution {RESOLUTION}")
        start = datetime.now(tz=timezone.utc)
        intervals = _get_intervals(start)
        loop = self.loop
        for resolution in intervals:
            snapshots = _generate_snapshot_range_historical(
                self.start_timestamp,
                resolution,
                intervals,
            )
            async for snapshot in snapshots:
                loop.create_task(self.export_historical_snapshot_if_missing(snapshot, resolution))
    
    # Export Methods
    
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
        logger.info(f"exported {self.name} snapshot %s block=%d took=%.3fs", snapshot, block, duration)
        await self._export_duration(duration, ts)
    
    async def export_historical_snapshot_if_missing(self, snapshot: datetime, resolution: Resolution) -> None:
        if not await self._has_data(snapshot):
            timestamp = int(snapshot.timestamp())
            block = await run_in_thread(closest_block_after_timestamp, timestamp)
            assert block is not None, "no block after timestamp found. timestamp: %s" % timestamp
            await self.export_snapshot(block, snapshot, resolution)
    
    # Datastore Methods

    async def _has_data(self, snapshot: datetime) -> bool:
        ts = snapshot.timestamp()
        async with self._has_data_semaphore:
            response = await has_data(ts, self.data_query)
        if response:
            logger.info(f"data already present for {self.name} snapshot {snapshot}, ts {ts}")
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
    
    # Snapshot Timestamp Generators
    
