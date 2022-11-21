import logging

import sentry_sdk
from y.networks import Network

from yearn.helpers.exporter import Exporter
from yearn.treasury.dask_helpers import treasury_data_for_export
from yearn.treasury.treasury import YearnTreasury

sentry_sdk.set_tag('script','treasury_exporter')

logger = logging.getLogger('yearn.treasury_exporter')

treasury = YearnTreasury(asynchronous=True)

exporter = Exporter(
    name = 'treasury',
    data_query = 'treasury_assets{network="' + Network.label() + '"}',
    data_fn = treasury_data_for_export,
    start_block = treasury._start_block,
)

def main():
    exporter.run()
