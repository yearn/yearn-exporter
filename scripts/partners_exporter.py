import logging
import os
import time

import sentry_sdk
from brownie import chain

from yearn.outputs.timescale import output_duration
from yearn.outputs.timescale.output_treasury import _get_symbol
from yearn.outputs.timescale.output_helper import _build_item, _post
from yearn.treasury.buckets import get_token_bucket
from yearn.partners.partners import partners

sentry_sdk.set_tag('script','partners_exporter')

logger = logging.getLogger('yearn.partners_exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))


def export_partners(block):
    for partner in partners:
        # collect payout data
        data, _ = partner.process()
        if len(data) == 0:
            continue
        data = data.loc[data.index <= block.number]

        # export wrapper data
        metrics_to_export = []
        for wrapper in set(data.wrapper):
            wrapper_info = {}

            wrapper_data = data[data.wrapper == wrapper]
            if len(wrapper_data) == 0:
                continue
            token = wrapper_data.vault.iloc[-1]
            symbol = _get_symbol(token)
            bucket = get_token_bucket(token)

            # wrapper balance
            wrapper_info["balance"] = float(wrapper_data.balance.iloc[-1])
            wrapper_info["balance_usd"] = float(wrapper_data.balance_usd.iloc[-1])

            # wrapper payouts
            wrapper_daily_data = wrapper_data.set_index('timestamp').resample('1D').sum()
            wrapper_info["payout_daily"] = float(wrapper_daily_data.payout.iloc[-1])
            wrapper_info["payout_weekly"] = float(wrapper_daily_data.payout.iloc[-7:].sum())
            wrapper_info["payout_monthly"] = float(wrapper_daily_data.payout.iloc[-30:].sum())
            wrapper_info["payout_total"] = float(wrapper_daily_data.payout.sum())
            wrapper_info["payout_usd_daily"] = float(wrapper_daily_data.payout_usd.iloc[-1])
            wrapper_info["payout_usd_weekly"] = float(wrapper_daily_data.payout_usd.iloc[-7:].sum())
            wrapper_info["payout_usd_monthly"] = float(wrapper_daily_data.payout_usd.iloc[-30:].sum())
            wrapper_info["payout_usd_total"] = float(wrapper_daily_data.payout_usd.sum())

            for key, value in wrapper_info.items():
                item = _build_item(
                    "partners",
                    ['partner', 'param', 'token_address', 'token', 'bucket'],
                    [partner.name, key, token, symbol, bucket],
                    value,
                    block.timestamp
                )
                metrics_to_export.append(item)
        _post(metrics_to_export)


def main():
    for block in chain.new_blocks(height_buffer=12):
        start_time = time.time()
        export_partners(block)
        duration = time.time() - start_time
        output_duration.export(duration, 1, "partners_forwards", block.timestamp)
        logger.info('exported block=%d took=%.3fs', block.number, time.time() - start_time)
        time.sleep(sleep_interval)
