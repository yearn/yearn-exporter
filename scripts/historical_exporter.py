import logging
import time
from datetime import datetime, timezone

import sentry_sdk
from brownie import chain
from yearn.historical_helper import export_historical, time_tracking
from yearn.networks import Network
from yearn.utils import closest_block_after_timestamp
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','historical_exporter')

logger = logging.getLogger('yearn.historical_exporter')

def main():
    start = datetime.now(tz=timezone.utc)
    if Network(chain.id) == Network.Fantom:
        # end: 2021-04-30 first possible date after the Fantom network upgrade
        end = datetime(2021, 4, 30, tzinfo=timezone.utc)
        # ironbank first product deployed on Fantom
        data_query = 'ironbank{network="FTM"}'
    elif Network(chain.id) == Network.Gnosis:
        # end: yvUSDC vault January-20-2022 06:10:45 AM +-6 UTC
        end = datetime(2022, 1, 20, tzinfo=timezone.utc)
        data_query = 'yearn_vault{network="GNO"}'
    elif Network(chain.id) == Network.Arbitrum:
        # end: yvUSDC 4.3 Sep-05-2021 09:05:50 PM +UTC
        end = datetime(2021, 9, 5, tzinfo=timezone.utc)
        data_query = 'yearn_vault{network="ARBB"}'
    elif Network(chain.id) == Network.Optimism:
        # end: yvDAI Aug-06-2022 10:50:49 PM +UTC block 18111485
        end = datetime(2022, 8, 6, tzinfo=timezone.utc)
        data_query = 'yearn_vault{network="OPT"}'
    else:
        # end: 2020-02-12 first iearn deployment
        end = datetime(2020, 2, 12, 0, 1, tzinfo=timezone.utc)
        data_query = 'iearn{network="ETH"}'

    export_historical(
        start,
        end,
        export_chunk,
        export_snapshot,
        data_query
    )


def export_chunk(chunk, export_snapshot_func):
    yearn = Yearn(watch_events_forever=False)
    for snapshot in chunk:
        ts = snapshot.timestamp()
        export_snapshot_func(
            {
                'yearn': yearn,
                'snapshot': snapshot,
                'ts': ts,
                'exporter_name': 'historical'
            }
        )

@time_tracking
def export_snapshot(yearn, snapshot, ts, exporter_name):
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    yearn.export(block, ts)
    logger.info("exported historical snapshot %s", snapshot)
