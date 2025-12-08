import logging
from datetime import datetime, timezone

import sentry_sdk
from y.constants import CHAINID
from y.networks import Network
from y.time import closest_block_after_timestamp

from yearn import constants
from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _post
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','vaults_exporter')

logger = logging.getLogger('yearn.vaults_exporter')

logging.getLogger("y._db.utils.logs").setLevel(logging.NOTSET)

yearn = Yearn()

if Network(CHAINID) == Network.Fantom:
    # end: 2021-04-30 first possible date after the Fantom network upgrade
    start = datetime(2021, 4, 30, tzinfo=timezone.utc)
    # ironbank first product deployed on Fantom
    data_query = 'ironbank{network="' + Network.label() + '"}'
elif Network(CHAINID) == Network.Gnosis:
    # end: yvUSDC vault January-20-2022 06:10:45 AM +-6 UTC
    start = datetime(2022, 1, 20, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="' + Network.label() + '"}'
elif Network(CHAINID) == Network.Arbitrum:
    # end: yvUSDC 4.3 Sep-05-2021 09:05:50 PM +UTC
    start = datetime(2021, 9, 5, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="' + Network.label() + '"}'
elif Network(CHAINID) == Network.Optimism:
    # end: yvDAI Aug-06-2022 10:50:49 PM +UTC block 18111485
    start = datetime(2022, 8, 6, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="' + Network.label() + '"}'
elif Network(CHAINID) == Network.Mainnet:
    # end: 2020-02-12 first iearn deployment
    start = datetime(2020, 2, 12, 0, 1, tzinfo=timezone.utc)
    data_query = 'iearn{network="' + Network.label() + '"}'
elif Network(CHAINID) == Network.Base:
    # end: release registry Aug-29-2023 01:37:43 PM +UTC block 3263458
    start = datetime(2023, 8, 29, tzinfo=timezone.utc)
    data_query = 'yearn_vault{network="' + Network.label() + '"}'
else:
    raise NotImplementedError()


exporter = Exporter(
    name = 'vaults',
    data_query = data_query,
    data_fn = yearn.data_for_export, 
    export_fn = _post,
    start_block = closest_block_after_timestamp(int(start.timestamp())) - 1,
    concurrency=constants.CONCURRENCY,
)

def main():
    exporter.run()
