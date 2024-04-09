import asyncio
import logging
from datetime import datetime, timezone

import sentry_sdk
from brownie import chain
from cachetools.func import ttl_cache
from y import Network
from y.time import closest_block_after_timestamp

from yearn import constants
from yearn.entities import UserTx
from yearn.helpers.exporter import Exporter
from yearn.outputs.postgres.utils import last_recorded_block
from yearn.outputs.victoria.victoria import _post
from yearn.utils import run_in_thread
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','wallet_exporter')

logger = logging.getLogger('yearn.wallet_exporter')

yearn = Yearn()

# start: 2020-02-12 first iearn deployment
# start opti: 2022-01-01 an arbitrary start timestamp because the default start is < block 1 on opti and messes things up
if chain.id in [Network.Arbitrum, Network.Optimism]:
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
elif Network.Base:
    start = datetime(2023, 9, 1, tzinfo=timezone.utc)
else:
    start = datetime(2020, 2, 12, tzinfo=timezone.utc)

@ttl_cache(ttl=60)
def get_last_recorded_block():
    return last_recorded_block(UserTx)

def postgres_ready(snapshot: datetime) -> bool:
    if (postgres_cached_thru_block := get_last_recorded_block()):
        return chain[postgres_cached_thru_block].timestamp >= snapshot.timestamp()
    logger.debug("postgress not yet popuated for %s", snapshot)
    return False

class WalletExporter(Exporter):
    async def export_historical_snapshot(self, snapshot: datetime) -> None:
        """ Override a method on Exporter so we can add an additional check. """
        if await run_in_thread(postgres_ready, snapshot):
            return await super().export_historical_snapshot(snapshot)

exporter = WalletExporter(
    name = "wallets",
    data_query = 'aggregate{param="total wallets", network="' + Network.label() + '"}',
    data_fn = yearn.wallet_data_for_export,
    export_fn = _post,
    start_block = closest_block_after_timestamp(int(start.timestamp())) - 1,
    concurrency=constants.CONCURRENCY,
)

def main():
    exporter.run("historical")
    raise Exception("Don't mind me, just restarting the container")
