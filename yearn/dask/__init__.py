
import logging
import os
from functools import lru_cache
from typing import List

from dask import delayed

BROWNIE_NETWORK = os.environ.get("BROWNIE_NETWORK_ID", "")

from dask import config
from dask.distributed import Client

logger = logging.getLogger('yearn.dask')

@lru_cache(1)
def _get_client_from_worker():
    config.set({"distributed.worker.daemon": False})
    config.set({"distributed.scheduler.worker-ttl": None})
    return ChainAwareClient("tcp://scheduler:8786")

class ChainAwareClient(Client):
    """A dask client that will only submit tasks to works running on the same chainid."""
    # NOTE: We don't want to cache these properties since workers can go offline
    @property
    def workers(self) -> dict:
        return self._scheduler_identity["workers"]
    @property
    def workers_for_chain(self) -> List[str]:
        return [worker["id"] for worker in self.workers.values() if BROWNIE_NETWORK in worker["id"]]
    def submit(self, *args, **kwargs):
        return super().submit(*args, **self._apply_chain_constraint(kwargs))
    def compute(self, *args, **kwargs):
        return super().compute(*args, **self._apply_chain_constraint(kwargs))
    def _apply_chain_constraint(self, kwargs: dict) -> dict:
        # NOTE: You can bypass this constraint if necessary by passing your own `workers` kwarg.
        if "workers" not in kwargs:
            kwargs["workers"] = self.workers_for_chain
        return kwargs
