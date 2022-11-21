
import logging

import sentry_sdk
from brownie import chain
from y.networks import Network

from yearn.helpers.exporter import Exporter
from yearn.treasury.dask_helpers import sms_data_for_export

sentry_sdk.set_tag('script','sms_exporter')

logger = logging.getLogger('yearn.sms_exporter')

exporter = Exporter(
    name = 'sms',
    data_query = 'sms_assets{network="' + Network.label() + '"}',
    data_fn = sms_data_for_export,
    start_block = {
        Network.Mainnet: 11_507_716,
        Network.Fantom: 10_836_306,
        Network.Gnosis: 20_455_212,
        Network.Arbitrum: 2_434_174,
        Network.Optimism: 18_084_577,
    }[chain.id],
)

def main():
    exporter.run()
