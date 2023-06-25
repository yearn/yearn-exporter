import logging

import sentry_sdk
from y.networks import Network

from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _post
from yearn.treasury.treasury import YearnTreasury

sentry_sdk.set_tag('script','treasury_exporter')

logger = logging.getLogger('yearn.treasury_exporter')

treasury = YearnTreasury(asynchronous=True)

exporter = Exporter(
    name = 'treasury',
    data_query = 'treasury_assets{network="' + Network.label() + '"}',
    data_fn = treasury.data_for_export,
    export_fn = _post,
    start_block = treasury._start_block,
    concurrency=3,
)

def main():
    exporter.run()
