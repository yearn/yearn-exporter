import logging
from datetime import datetime, timezone

import sentry_sdk
from brownie import chain
from yearn.historical_helper import export_historical, time_tracking
from yearn.networks import Network
from yearn.treasury.treasury import StrategistMultisig
from yearn.utils import closest_block_after_timestamp

sentry_sdk.set_tag('script','historical_sms_exporter')

logger = logging.getLogger('yearn.historical_sms_exporter')


def main():
    data_query = 'sms_assets{network="' + Network.label() + '"}'
    start = datetime.now(tz=timezone.utc)
    
    end = {
        Network.Mainnet: datetime(2021, 1, 28, 9, 10, tzinfo=timezone.utc), # first inbound sms tx
        Network.Fantom: datetime(2021, 6, 17, tzinfo=timezone.utc), # Fantom SMS deployed
        Network.Gnosis: datetime(2022, 2, 3, 23, 45, tzinfo=timezone.utc), # Block 20455212, first tx in SMS
        Network.Arbitrum: datetime(2022, 10, 21, 9, 20, 38, tzinfo=timezone.utc) # https://arbiscan.io/tx/0x9f8de852b7bfb3122469fbd846fd3367db77a9d6399d61ba65224958af101066
    }[chain.id]

    export_historical(
        start,
        end,
        export_chunk,
        export_snapshot,
        data_query
    )
    
    
def export_chunk(chunk, export_snapshot_func):
    sms = StrategistMultisig()
    for snapshot in chunk:
        ts = snapshot.timestamp()
        export_snapshot_func(
            {
                'treasury': sms,
                'snapshot': snapshot,
                'ts': ts,
                'exporter_name': 'historical_sms'
            }
        )   


@time_tracking
def export_snapshot(sms, snapshot, ts, exporter_name):
    block = closest_block_after_timestamp(ts)
    assert block is not None, "no block after timestamp found"
    sms.export(block, ts)
    logger.info("exported SMS snapshot %s", snapshot)


