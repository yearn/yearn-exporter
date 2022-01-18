import itertools
import logging
from datetime import datetime, timezone
from typing import Union
from brownie import web3

from yearn.apy import ApyError, get_samples
from yearn.apy.common import ApySamples
from yearn.historical_helper import export_historical, time_tracking
from yearn.networks import Network
from yearn.v1.registry import Registry as RegistryV1
from yearn.v1.vaults import VaultV1
from yearn.v2.registry import Registry as RegistryV2
from yearn.v2.vaults import Vault as VaultV2

logger = logging.getLogger("yearn.historical_vault_apy")
END_DATE = {
    Network.Mainnet: datetime(
        2020, 2, 12, tzinfo=timezone.utc
    ),  # first iearn deployment
}

v1_registry = RegistryV1()
v2_registry = RegistryV2()

def main():
    start = datetime.now(tz=timezone.utc)
    end = END_DATE[Network.Mainnet]
    data_query = 'yearn_vault{param="net_apy"}'
    export_historical(
        start,
        end,
        export_chunk,
        export_snapshot,
        data_query
    )


def export_chunk(chunk, export_snapshot_func):

    for snapshot in chunk:
        ts = snapshot.timestamp()
        samples: ApySamples = get_samples(now_time=snapshot)
        logger.info("Exporting snapshot for chunk")
        for vault in itertools.chain(v1_registry.vaults, v2_registry.vaults):
            export_snapshot_func(
                {
                    'vault': vault,
                    'samples': samples,
                    'snapshot': snapshot,
                    'ts': ts,
                    'exporter_name': 'historical_apy',
                }
            )


@time_tracking
def export_snapshot(vault: Union[VaultV1, VaultV2], samples: ApySamples, snapshot, ts, exporter_name):
    try:
        vault.export_apy(samples, ts)
        logger.info("exported historical apy for vault %s, snapshot %s", vault.name, snapshot)
    except ApyError as e:
        logger.info("apy error occured.")
        logger.error(e)
