import asyncio
import logging
import os
import time
import sentry_sdk
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import (Awaitable, Callable, Literal, NoReturn, Optional, TypeVar,
                    overload)

import eth_retry
from brownie import chain
from dank_mids.controller import instances
from y.networks import Network
from y.time import closest_block_after_timestamp_async

from yearn import constants
from yearn.helpers.snapshots import (RESOLUTION,
                                     _generate_snapshot_range_forward,
                                     _generate_snapshot_range_historical,
                                     _get_intervals)
from yearn.outputs.victoria.victoria import _build_item, _post, has_data
from yearn.sentry import log_exceptions

logger = logging.getLogger(__name__)

SHOW_STATS = bool(os.environ.get("SHOW_STATS"))

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
        concurrency: Optional[int] = 1,
        resolution: Literal = RESOLUTION
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
        self.full_name = f"{Network.name()} {self.name}"
        self.data_query = data_query
        self.start_block = start_block
        self.start_timestamp = datetime.fromtimestamp(chain[start_block].timestamp, tz=timezone.utc)
        if resolution != RESOLUTION:
            logger.warn(f"{self.full_name}: Overriding resolution with custom value '{resolution}', env has '{RESOLUTION}' !")
        self._resolution = resolution

        self._data_fn = data_fn
        self._export_fn = eth_retry.auto_retry(export_fn)
        self._snapshots_fetched = 0
        self._snapshots_exported = 0
        self._semaphore = asyncio.Semaphore(concurrency)
    
    @overload
    def run(self, direction: Literal["historical"] = "historical") -> None:
        ...
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

    @cached_property
    def _start_time(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    # Export Sequences

    async def export_full(self) -> NoReturn:
        """ Exports all present, historical and future data. This coroutine will run forever. """
        # the history and future exports are run concurrently
        await asyncio.gather(self.export_history(), self.export_future())

    async def export_future(self) -> NoReturn:
        """ Exports all future data. This coroutine will run forever. """
        intervals = _get_intervals(self._start_time, self._resolution)
        start = intervals[self._resolution]['start']
        interval = intervals[self._resolution]['interval']
        # Bump forward to the next snapshot, as the historical coroutine will take care of this one.
        start = start + interval
        async for snapshot in _generate_snapshot_range_forward(start, interval):
            asyncio.create_task(self.export_snapshot(snapshot))

    async def export_history(self) -> None:
        """ Exports all historical data. This coroutine runs for a finite duration. """
        intervals = _get_intervals(self._start_time, self._resolution)
        for resolution in intervals:
            snapshot_generator = _generate_snapshot_range_historical(self.start_timestamp, resolution, intervals)
            await asyncio.gather(*[self.export_historical_snapshot(snapshot) async for snapshot in snapshot_generator])
        logger.info(f"historical {self.full_name} export complete in {self._get_runtime(datetime.now(tz=timezone.utc))}")

    @log_exceptions
    async def export_snapshot(self, snapshot: datetime) -> None:
        with sentry_sdk.start_transaction(op="task", name="export_snapshot"):
            start = time.time()
            timestamp = int(snapshot.timestamp())
            block = await closest_block_after_timestamp_async(timestamp, wait_for_block_if_needed=True)
            data = await self._data_fn(block, timestamp)
            duration = time.time() - start
            logger.info(f"produced {self.full_name} snapshot %s block=%d took=%.3fs", snapshot, block, duration)
            await asyncio.gather(self._export_data(data), self._export_duration(duration, snapshot.timestamp()))
            #logger.info(f"exported {self.full_name} snapshot %s block=%d took=%.3fs", snapshot, block, time.time() - start)
            self._record_stats()

    @log_exceptions
    async def export_historical_snapshot(self, snapshot: datetime) -> None:
        async with self._semaphore:
            if not await self._has_data(snapshot):
                await self.export_snapshot(snapshot)

    # Datastore Methods

    async def _has_data(self, snapshot: datetime) -> bool:
        with sentry_sdk.start_transaction(op="task", name="_has_data"):
            ts = snapshot.timestamp()
            response = await has_data(ts, self.data_query)
            if response:
                logger.info(f"data already present for {self.full_name} snapshot {snapshot}, ts {ts}")
            return bool(response)

    async def _export_data(self, data: T) -> None:
        with sentry_sdk.start_transaction(op="task", name="_export_data"):
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
                
    # Stats helpers
    
    def _record_stats(self) -> None:
        self._snapshots_fetched += 1
        if SHOW_STATS:
            logger.info(f"exported {self._snapshots_fetched} {self.full_name} snapshots in 'TODO: FIX' requests in {self._get_runtime()}")
            logger.info(f"avg rate of {self._get_requests_per_snapshot()} requests per snapshot. Currently only considers eth_calls.")
            logger.info(f"avg rate of {self._get_time_per_snapshot()} per {self.full_name} snapshot")
    
    def _get_runtime(self, start: Optional[datetime] = None) -> timedelta:
        return datetime.now(tz=timezone.utc) - (start or self._start_time)
    
    def _get_time_per_snapshot(self) -> timedelta:
        return self._get_runtime() / self._snapshots_fetched
    
    def _get_requests_per_snapshot(self) -> float:
        # TODO: Fix
        #return round(instances[0].worker.request_uid.latest / self._snapshots_fetched, 2)
        pass
