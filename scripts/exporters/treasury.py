import logging

import sentry_sdk
from brownie import chain
from y.networks import Network

from yearn.helpers.exporter import Exporter
from yearn.treasury.dask_helpers import treasury_data_for_export

sentry_sdk.set_tag('script','treasury_exporter')

logger = logging.getLogger('yearn.treasury_exporter')

exporter = Exporter(
    name = 'treasury',
    data_query = 'treasury_assets{network="' + Network.label() + '"}',
    data_fn = treasury_data_for_export,
    start_block = {
        Network.Mainnet: 10_502_337, # first treasury tx
        Network.Fantom: 18_950_072, # Fantom Multisig deployed
        Network.Gnosis: 20_000_000, # some time near the first tx in the Gnosis treasury EOA. Further testing is needed to confirm as first tx was not fully apparent on block explorer.
        Network.Arbitrum: 4_837_859, # first treasury tx
        Network.Optimism: 18_100_336, # create contract block
    }[chain.id],
)

def main():
    exporter.run()
