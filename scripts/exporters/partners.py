# NOTE: make sure that the partner exporter runs on a single process
import os
os.environ["POOL_SIZE"] = "1"

import logging
from datetime import datetime, timezone
from time import time

import sentry_sdk
from brownie import chain
from yearn.networks import Network
from yearn.outputs.victoria import output_duration
from yearn.outputs.victoria.output_helper import _build_item, _post
from yearn.outputs.victoria.output_treasury import _get_symbol
from yearn.partners.partners import partners
from yearn.snapshot_range_helper import (start_bidirectional_export,
                                         time_tracking)
from yearn.treasury.buckets import get_token_bucket
from yearn.utils import closest_block_after_timestamp

sentry_sdk.set_tag('script','partners_exporter')

logger = logging.getLogger('yearn.partners_exporter')


def main():
    data_query = 'partners{network="' + Network.label() + '"}'
    # This is forward-only
    start_bidirectional_export(datetime.now(tz=timezone.utc), export_snapshot, data_query)


@time_tracking
def export_snapshot(snapshot, ts):
    start = time()
    block = chain[closest_block_after_timestamp(snapshot.timestamp(), wait_for=True)]
    export_partners(block)
    duration = time() - start
    output_duration.export(duration, 1, "partners", block.timestamp)
    logger.info("exported partners snapshot %s took %.3fs", snapshot, time() - start)


def export_partners(block):
    # for partner in partners:
    for partner in partners:
        # collect payout data
        data, _ = partner.process()
        if len(data) == 0:
            continue
        data = data.loc[data.index <= block.number]

        # export wrapper data
        metrics_to_export = []
        for wrapper in set(data.wrapper):
            wrapper_data = data[data.wrapper == wrapper]

            # iterate over vault addresses
            for vault in set(wrapper_data.vault):
                wrapper_vault_data = wrapper_data[wrapper_data.vault == vault]
                symbol = _get_symbol(vault)
                bucket = get_token_bucket(vault)

                # placeholder for the wrapper-vault level info
                wrapper_vault_info = {}

                # wrapper balance
                wrapper_vault_info["balance"] = float(wrapper_vault_data.balance.iloc[-1])
                wrapper_vault_info["balance_usd"] = float(wrapper_vault_data.balance_usd.iloc[-1])

                # wrapper payouts
                daily_data = wrapper_vault_data.set_index('timestamp').resample('1D').sum()
                wrapper_vault_info["payout_daily"] = float(daily_data.payout.iloc[-1])
                wrapper_vault_info["payout_weekly"] = float(daily_data.payout.iloc[-7:].sum())
                wrapper_vault_info["payout_monthly"] = float(daily_data.payout.iloc[-30:].sum())
                wrapper_vault_info["payout_total"] = float(daily_data.payout.sum())
                wrapper_vault_info["payout_usd_daily"] = float(daily_data.payout_usd.iloc[-1])
                wrapper_vault_info["payout_usd_weekly"] = float(daily_data.payout_usd.iloc[-7:].sum())
                wrapper_vault_info["payout_usd_monthly"] = float(daily_data.payout_usd.iloc[-30:].sum())
                wrapper_vault_info["payout_usd_total"] = float(daily_data.payout_usd.sum())

                for key, value in wrapper_vault_info.items():
                    item = _build_item(
                        "partners",
                        ['partner', 'wrapper', 'param', 'token_address', 'token', 'bucket'],
                        [partner.name, wrapper, key, vault, symbol, bucket],
                        value,
                        block.timestamp
                    )
                    metrics_to_export.append(item)

        _post(metrics_to_export)
