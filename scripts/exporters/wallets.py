import asyncio
import logging
from datetime import datetime, timezone

import sentry_sdk
from brownie import chain
from cachetools.func import ttl_cache
from y.time import closest_block_after_timestamp
from yearn.entities import UserTx
from yearn.helpers.exporter import Exporter
from yearn.outputs.postgres.utils import last_recorded_block
from yearn.outputs.victoria.victoria import _post
from yearn.utils import run_in_thread
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','wallet_exporter')

logger = logging.getLogger('yearn.wallet_exporter')

yearn = Yearn(watch_events_forever=False)

# start: 2020-02-12 first iearn deployment
start = datetime(2020, 2, 12, tzinfo=timezone.utc)

@ttl_cache(ttl=60)
def get_last_recorded_block():
    return last_recorded_block(UserTx)

def postgres_ready(snapshot: datetime) -> bool:
    if (postgres_cached_thru_block := get_last_recorded_block()):
        return chain[postgres_cached_thru_block].timestamp >= snapshot.timestamp()
    return False

# TODO daskify this one
class WalletExporter(Exporter):
    async def export_snapshot(self, snapshot: datetime, resolution: str) -> None:
        """ Override a method on Exporter so we can add an additional check. """
        if await run_in_thread(postgres_ready, snapshot):
            return await super().export_historical_snapshot_if_missing(snapshot, resolution)

exporter = WalletExporter(
    name = "wallets",
    data_query = 'aggregate{param="total wallets"}',
    data_fn = yearn.wallet_data_for_export,
    export_fn = _post,
    start_block = closest_block_after_timestamp(int(start.timestamp())) - 1,
    max_concurrent_runs = 2, # The wallet exporter uses a lot of memory, so we must limit concurrency here
    stop=True
)

def main():
    exporter.run("historical")
