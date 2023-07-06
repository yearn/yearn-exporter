import asyncio
from typing import List, Tuple

import sentry_sdk
from brownie import chain
from eth_portfolio.buckets import get_token_bucket
from pandas import DataFrame
from y.networks import Network
from y.time import closest_block_after_timestamp

from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _build_item, _post
from yearn.partners.partners import partners
from yearn.treasury.treasury import _get_symbol

sentry_sdk.set_tag('script','partners_exporter')

def main():
    # If there are no partners for this chain, exit with success.
    if not partners:
        return
    
    start = {
        # 2021-01-19 time of earliest block with partner_tx for Ethereum network
        Network.Mainnet: 1611017667,
        # 2021-10-26 block time of earliest block with partner_tx for Fantom network
        Network.Fantom: 1635263041,
    }[chain.id]
    
    exporter = Exporter(
        name = 'partners',
        data_query = 'partners{network="' + Network.label() + '"}',
        data_fn = export_partners,
        export_fn = _post,
        start_block = closest_block_after_timestamp(start) - 1,
        concurrency=1,
    )
    
    exporter.run()

async def export_partners(block, ts):
    # collect payout data
    partners_data: List[Tuple[DataFrame, DataFrame]] = await asyncio.gather(*[partner.process() for partner in partners])

    # export wrapper data
    metrics_to_export = []
    for partner, (partner_data, _) in zip(partners, partners_data):
        if len(partner_data) == 0:
            continue
        partner_data = partner_data.loc[partner_data.index <= block]

        for wrapper in set(partner_data.wrapper):
            wrapper_info = {}

            wrapper_data = partner_data[partner_data.wrapper == wrapper]
            if len(wrapper_data) == 0:
                continue
            token = wrapper_data.vault.iloc[-1]
            symbol, bucket = await asyncio.gather(_get_symbol(token), get_token_bucket(token))

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
                    ts,
                )
                metrics_to_export.append(item)
    return metrics_to_export
