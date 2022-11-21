
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import (Any, Awaitable, Callable, Dict, List, Literal, NoReturn,
                    Optional, Tuple, TypeVar)

import dask
from brownie import chain
from dask.delayed import Delayed
from eth_portfolio.utils import get_buffered_chain_height
from y.datatypes import Block
from y.networks import Network
from y.time import closest_block_after_timestamp_async
from y.utils.dank_mids import dank_w3

from yearn.dask import ChainAwareClient, _get_client_from_worker
from yearn.helpers.snapshots import (RESOLUTION, SLEEP_TIME,
                                     _generate_snapshot_range_forward,
                                     _generate_snapshot_range_historical,
                                     _get_intervals)
from yearn.outputs.victoria.victoria import _build_item, _to_jsonl_gz, has_data

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
SHOW_STATS = bool(os.environ.get("SHOW_STATS"))

@dask.delayed(pure=False)
async def _wait_for_block(timestamp: int) -> Block:
    # eth_retry decorated functions can't be pickled.
    import eth_retry
    while True:
        block = await dank_w3.eth.get_block(await get_buffered_chain_height())
        while timestamp < block.timestamp:
            try:
                prev_block = await eth_retry.auto_retry(dank_w3.eth.get_block)(block.number - 1)
                if prev_block.timestamp < timestamp:
                    return block.number
                block = prev_block
            except ValueError as e:
                if 'parse error' not in str(e):
                    raise
        await asyncio.sleep(SLEEP_TIME)

T = TypeVar('T')
Direction = Literal["forward", "historical"]
vm_semaphore = asyncio.Semaphore(1)

def _clear_completed_futures(futs: list):
    for fut in futs:
        if fut.status == "finished":
            futs.pop(fut)

@dask.delayed
async def get_block_if_missing(snapshot: datetime, has_data: bool) -> Optional[int]:
    if not has_data:
        timestamp = int(snapshot.timestamp())
        return await closest_block_after_timestamp_async(timestamp)

#@log_task_exceptions
def export_snapshot(self, block: int, snapshot: datetime) -> Delayed:
    """ Assembles a dask.Delayed object containing the export logic and submits it to the scheduler. """ 
    #data, duration = dask.delayed(get_data, name=f"get {Network.name()} {self.name} data", nout=2, pure=False)(block, snapshot, self._data_fn)
    data, duration = self._data_fn(block, int(snapshot.timestamp()))
    data = dask.delayed(self._export_fn, name="push to datastore")(data)    
    duration = dask.delayed(self._export_duration, name="export duration")(block, duration, snapshot.timestamp())
    # TODO add _print_stats in _success_msg
    return dask.delayed(self._success_msg)(block, snapshot, duration, data) # NOTE We tuck `data` in here to force dask to confirm success before returning the log message

_has_data_semaphore = asyncio.Semaphore(2)

@dask.delayed
async def _has_data(name: str, data_query, snapshot: datetime) -> bool:
    ts = snapshot.timestamp()
    async with _has_data_semaphore:
        response = await has_data(ts, data_query)
    if response:
        logger.info(f"data already present for {Network.name()} {name} snapshot {snapshot}, ts {ts}")
    return bool(response)

'''
async def get_data(block: int, snapshot: datetime, _data_fn): # -> Tuple[T, int]:
    if block is None:
        return [], 0
    start = time.time()
    ts = snapshot.timestamp()
    data = await _data_fn(block, ts)
    duration = time.time() - start
    logger.info(data)
    #self._snapshots_fetched += 1
    return data, duration
'''
_export_semaphore = asyncio.Semaphore(2)

@dask.delayed(pure=False)
async def _export_data(_export_fn, data: T) -> None:
    from yearn.dask import _get_client_from_worker

    #async with _export_semaphore:
        #await eth_retry.auto_retry(_post if _export_fn is None else _export_fn)(url, data)
    fut = _get_client_from_worker().submit(_post if _export_fn is None else _export_fn, BASE_URL, data, asynchronous=True)
    await fut
    #self._snapshots_exported += 1


#@dask.delayed

async def _post(metrics_to_export: List[Dict]) -> None:
    import aiohttp
    """ Post all metrics at once."""
    '''
    if isinstance(metrics_to_export, Delayed):
        metrics_to_export = await client.compute(metrics_to_export, asynchronous=True)
    while asyncio.iscoroutine(metrics_to_export):
        metrics_to_export = await metrics_to_export'''

    if not metrics_to_export:
        return metrics_to_export
    IMPORT_URL = f'{BASE_URL}/api/v1/import'
    VM_REQUEST_HEADERS = {'Connection': 'close', 'Content-Encoding': 'gzip'}
    data = _to_jsonl_gz(metrics_to_export)
    attempts = 0
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    url = IMPORT_URL,
                    headers = VM_REQUEST_HEADERS,
                    data = data,
                )
            return data
        except Exception as e:
            if not isinstance(e, aiohttp.ClientError):
                raise e
            attempts += 1
            logger.debug(f'You had a ClientError: {e}')
            if attempts >= 10:
                raise e



class Exporter:
    """ Currently can only be used to output to victoria metrics. Can be extended for other data sources. """
    
    def __init__(
        self,
        name: str,
        data_query: str,
        data_fn: Callable[[int, int], Awaitable[T]], 
        start_block: int,
        export_fn: Callable[[T], Awaitable[None]] = _post,
        max_concurrent_runs: int = 10 * int(os.environ.get("POOL_SIZE", 1)),
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
        self.chain_id = chain.id
        self.data_query = data_query
        self.start_block = start_block
        self.start_timestamp = datetime.fromtimestamp(chain[start_block].timestamp, tz=timezone.utc)

        self._data_fn = data_fn
        self._export_fn = export_fn
        self._concurrency = max_concurrent_runs
        #self._data_semaphore = asyncio.Semaphore(self._concurrency)
        #self._res_semaphore = defaultdict(lambda: asyncio.Semaphore(max_concurrent_runs_per_resolution))
        #self._has_data_semaphore = asyncio.Semaphore(2)
        #self._export_semaphore = asyncio.Semaphore(2)
        self._futs = []
        
        self._snapshots_fetched = 0
        self._snapshots_exported = 0
    
    def __hash__(self) -> int:
        return self.chain_id
    
    def run(self, direction: Optional[Direction] = None) -> NoReturn:
        client = ChainAwareClient("tcp://scheduler:8786")
        if direction is None:
            client.submit(self.export_full, key=f"{self.name} full {Network.name()}").result()
        elif direction == "forward":
            client.submit(self.export_future, key=f"{self.name} full {Network.name()}").result()
        elif direction == "historical":
            client.submit(self.export_history, key=f"{self.name} full {Network.name()}").result()
        else:
            raise NotImplementedError(f'`direction` must be one of either `None`, `"forward"`, or `"historical"`. You passed {direction}')
    
    @property
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
        futs = []
        async for snapshot in _generate_snapshot_range_forward(start, interval):
            block = _wait_for_block(snapshot.timestamp())
            delayed = export_snapshot(self, block, snapshot)
            futs.append(_get_client_from_worker().compute(delayed, asynchronous=True))
            _clear_completed_futures(futs)

    async def export_history(self) -> None:
        """ Exports all historical data. This coroutine runs for a finite duration. """
        logger.info(f"exporting {Network.name()} {self.name} snapshots for resolution {RESOLUTION}")
        start = datetime.now(tz=timezone.utc)
        intervals = _get_intervals(start)
        delayeds = []
        for resolution in intervals:
            snapshots = _generate_snapshot_range_historical(
                self.start_timestamp,
                resolution,
                intervals,
            )
            async for snapshot in snapshots:
                exists = await has_data(snapshot.timestamp(), self.data_query)
                block = get_block_if_missing(snapshot, exists)
                delayeds.append(export_snapshot(self, block, snapshot))
                
            futs = _get_client_from_worker().compute(delayeds, asynchronous=True)
            
            
            #futs = _get_client_from_worker().compute(delayeds[:self._concurrency], asynchronous=True)
            #delayeds = delayeds[self._concurrency:]
            errd_futs = []
            #while delayeds:
            #    if len(futs) < self._concurrency:
            #        futs.append(_get_client_from_worker().compute(delayeds.pop(0)))
            while futs:    
                for i, fut in enumerate(futs):
                    if fut.status == "finished":
                        self._log_future_result(fut)
                        futs.pop(i)
                    elif fut.status == "error":
                        # TODO maybe raise errs? 
                        errd_futs.append(futs.pop(i))
                await asyncio.sleep(1)

    def _log_future_result(self, fut) -> None:
        log_msg = fut.result()
        self._snapshots_fetched += 1
        self._snapshots_exported += 1
        if isinstance(log_msg, tuple):
            logger.info(*log_msg)
        else:
            logger.info(log_msg)
        
        #batches = [delayeds[i:i+self._concurrency] for i in range(0, len(delayeds), self._concurrency)]
        #for batch in batches:
        #    futs = _get_client().compute(batch, asynchronous=True)
        #    await _get_client().gather(futs, errors="skip",asynchronous=True) #errors="skip", asynchronous=True)
    
    # Export Methods
    
    '''
    @dask.delayed(nout=2, pure=False)
    async def get_data(self, block: int, snapshot: datetime) -> Tuple[T, int]:
        start = time.time()
        ts = snapshot.timestamp()
        data = self._data_fn(block, ts)
        # If `data` is a Delayed object, we can pass it thru as-is
        if self.name != "vaults":
            data = await data
        duration = time.time() - start
        self._snapshots_fetched += 1
        return data, duration
    '''
    # Datastore Methods

    async def _export_duration(self, block, duration_seconds: float, timestamp_seconds: float) -> float:
        if block is None:
            return
        item = _build_item(
            "export_duration",
            [ "concurrency", "exporter" ],
            [ self._concurrency, self.name ],
            duration_seconds,
            timestamp_seconds
            )
        await _post([item])
        return duration_seconds
    
    # Stats
    @dask.delayed
    async def _print_stats(self, _: "dask.Delayed") -> None:  # type: ignore
        if SHOW_STATS:
            snapshots = self._snapshots_fetched
            # does it work if I comment this out? 
            #requests = instances[0].worker.request_uid.latest
            #logger.info(f"exported {snapshots} snapshots in {requests} requests")
            #logger.info(f"Avg rate of {round(requests/snapshots, 2)} requests per snapshot. Currently only considers eth_calls.")
    
    async def _success_msg(self, block: int, snapshot: datetime, duration: float, data: Any) -> Tuple[str, Optional[float]]:
        if block is None:
            return f"data already present for {Network.name()} {self.name} snapshot {snapshot}, ts {int(snapshot.timestamp())}"
        if not data:
            logger.info(f"No data for block {block}. This shouldn't happen, you might want to move the `start_block`.")
        return f"exported {Network.name()} {self.name} snapshot {snapshot} block={block} took=%.3fs", duration
    
    # Snapshot Timestamp Generators
    
