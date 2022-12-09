
import asyncio
import logging
from datetime import datetime, timezone
from functools import lru_cache
from time import time
from typing import TYPE_CHECKING, Tuple

import dask
import sentry_sdk
from brownie import chain
from dask.delayed import Delayed
from dask.distributed import get_worker
from y.networks import Network
from y.time import closest_block_after_timestamp

from yearn.dask import _get_async_client, use_chain_semaphore
from yearn.helpers.exporter import Exporter

if TYPE_CHECKING:
    from yearn.yearn import Yearn

#from yearn.outputs.victoria.victoria import _post

sentry_sdk.set_tag('script','vaults_exporter')

logger = logging.getLogger('yearn.vaults_exporter')



if Network(chain.id) == Network.Fantom:
    # end: 2021-04-30 first possible date after the Fantom network upgrade
    start = datetime(2021, 4, 30, tzinfo=timezone.utc)
    # ironbank first product deployed on Fantom
    data_query = 'ironbank{network="FTM"}'
elif Network(chain.id) == Network.Gnosis:
    # end: yvUSDC vault January-20-2022 06:10:45 AM +-6 UTC
    start = datetime(2022, 1, 20, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="GNO"}'
elif Network(chain.id) == Network.Arbitrum:
    # end: yvUSDC 4.3 Sep-05-2021 09:05:50 PM +UTC
    start = datetime(2021, 9, 5, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="ARB"}'
elif Network(chain.id) == Network.Optimism:
    # end: yvDAI Aug-06-2022 10:50:49 PM +UTC block 18111485
    start = datetime(2022, 8, 6, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="OPT"}'
elif Network(chain.id) == Network.Mainnet:
    # end: 2020-02-12 first iearn deployment
    start = datetime(2020, 2, 12, 0, 1, tzinfo=timezone.utc)
    data_query = 'iearn{network="ETH"}'
else:
    raise NotImplementedError()


def data_for_export(block, timestamp) -> Delayed:
    worker, yearn = _import_yearn()
    delayed = _export_vaults(worker, yearn, block, timestamp)
    return delayed

exporter = Exporter(
    name = 'vaults',
    data_query = data_query,
    data_fn = data_for_export, 
    start_block = closest_block_after_timestamp(int(start.timestamp())) - 1,
)

def main():
    exporter.run()

@dask.delayed(nout=2)
@use_chain_semaphore(1)
def _import_yearn() -> Tuple[str, "Yearn"]:
    """ A helper function to allow dask workers to cache the Yearn object in memory from a subthread. """
    imported_on_worker = get_worker().id
    return imported_on_worker, __import_yearn()

@lru_cache(1)
def __import_yearn() -> "Yearn":
    """ You can't stack the lru_cache decorator with use_chain_semaphore. """
    # This has trouble being imported with Yearn unless we import it first. Odd.
    from yearn.utils import contract
    # Importing yearn takes a while and blocks the event loop, so we do it in a thread.
    from yearn.yearn import Yearn
    return Yearn()


@dask.delayed(nout=2)
async def _export_vaults(worker: str, yearn: "Yearn", block, timestamp):
    """ Since we import the Yearn object in a worker subthread, we want to export on the same worker so we know it has the required imports. """
    client = await _get_async_client()
    start = time()
    v2_vaults = await yearn.registries["v2"].active_vaults_at(block)
    strats = await asyncio.gather(*[vault.strategies for vault in v2_vaults])
    v2_vaults = [(vault, strats) for vault, strats in zip(v2_vaults, strats)]
    
    data = yearn.describe_delayed(block, v2_vaults)
    fut = client.compute(
        yearn._data_for_export(block, timestamp, start, data),
        workers=[worker],
        asynchronous=True,
    )
    while not fut.status in ["finished", "error"]:
        await asyncio.sleep(0)
    data, duration = await fut
    return data, duration