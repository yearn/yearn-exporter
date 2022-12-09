
import asyncio
import functools
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Awaitable, Callable, List, TypeVar

from async_lru import alru_cache
from dask import delayed
from dask.distributed import Client, Semaphore
from typing_extensions import ParamSpec
from y import Network


logger = logging.getLogger('yearn.dask')

BROWNIE_NETWORK = os.environ.get("BROWNIE_NETWORK_ID", "")
CONCURRENCY = 20 #10 * int(os.environ.get("POOL_SIZE", 1))
DASK_SCHEDULER = "tcp://scheduler:8786"


@lru_cache(1)
def _get_sync_client() -> "ChainAwareClient":
    return ChainAwareClient(DASK_SCHEDULER)

@alru_cache(maxsize=1)
async def _get_async_client() -> "ChainAwareClient":
    return await ChainAwareClient(DASK_SCHEDULER, asynchronous=True)


class ChainAwareClient(Client):
    """A dask client that will only submit tasks to workers running on the same chainid."""
    # NOTE: We don't want to cache these properties since workers can go offline
    @property
    def workers(self) -> dict:
        return self._scheduler_identity["workers"]
    @property
    def workers_for_chain(self) -> List[str]:
        return [worker["id"] for worker in self.workers.values() if BROWNIE_NETWORK in worker["id"]]
    @property
    def first_worker_for_chain(self) -> str:
        return self.workers_for_chain[0]
    def submit(self, *args, **kwargs):
        return super().submit(*args, **self._apply_chain_constraint(kwargs))
    def compute(self, *args, **kwargs):
        return super().compute(*args, **self._apply_chain_constraint(kwargs))
    def _apply_chain_constraint(self, kwargs: dict) -> dict:
        # NOTE: You can bypass this constraint if necessary by passing your own `workers` kwarg.
        if "workers" not in kwargs:
            kwargs["workers"] = self.workers_for_chain
        return kwargs


P = ParamSpec("P")
T = TypeVar("T")

def use_chain_semaphore(concurrency: int) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Apply this decorator to an async function that will be turned into a dask.Delayed object
    if you want to limit the number of concurrent runs to `concurrency`

    Example:

    ```
    @use_chain_semaphore(100)
    async def cool_fn_you_need_to_limit():
        ...
    ```
    """

    def semaphore_decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        
        _get_sync_client()
        decoratee_semaphore = Semaphore(max_leases=concurrency, name=f"{fn.__module__}.{fn.__name__} {Network.name()}")

        async def _release_semaphore() -> None:
            # NOTE If we can't release the semaphore, the scheduler likely already has due to lease timeout.
            #      No biggie. But we should still try.
            try:
                await decoratee_semaphore.release()
            except RuntimeError as e:
                if str(e) != "Released too often":
                    raise
        
        @functools.wraps(fn)
        async def semaphore_wrap(*args, **kwargs) -> T:
            await decoratee_semaphore.acquire()
            try:
                if asyncio.iscoroutinefunction(fn):
                    retval = await fn(*args, **kwargs)
                else:
                    retval = await asyncio.get_event_loop().run_in_executor(ThreadPoolExecutor(1), fn, *args, **kwargs)
                await _release_semaphore()
                return retval
            except Exception as e:
                await _release_semaphore()
                raise e
        return semaphore_wrap

    return semaphore_decorator
