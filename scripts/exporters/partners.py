import asyncio
import time
from datetime import date
from typing import List, Optional, Tuple

import dask
import sentry_sdk
from brownie import chain
from dask.delayed import Delayed
from eth_portfolio.buckets import get_token_bucket
from pandas import DataFrame
from y.networks import Network

from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _build_item
from yearn.partners.partners import Partner, Wrapper, partners
from yearn.treasury.dask_helpers import _get_symbol

sentry_sdk.set_tag('script','partners_exporter')

PartnerParams = Tuple[str, date, List[Wrapper], Optional[str], List[str]]

def export_partners(block, ts) -> Delayed:
    # NOTE: We can't pickle the partner object so we will recreate it in the worker.
    partner_params: List[PartnerParams] = [(partner.name, partner.start_date, partner.wrappers, partner.treasury, partner.retired_treasuries) for partner in partners]
    return collect_partners([fetch_data_for_partner(params, block, ts) for params in partner_params])

@dask.delayed(nout=2)
async def fetch_data_for_partner(params: PartnerParams, block, ts) -> Tuple[List[dict], int]:
    # This fixes an ImportError on the dask worker.
    from yearn.utils import contract

    partner = Partner(*params)
    start = time.time()
    data, _ = await partner.process()
    if len(data) == 0:
        return [], start

    data = data.loc[data.index <= block]

    # export wrapper data
    metrics_to_export = []
    if len(data):
        wrappers = set(data.wrapper)
        details = await asyncio.gather(*[asyncio.gather(_get_symbol(wrapper), get_token_bucket(wrapper)) for wrapper in wrappers])
        for wrapper, (symbol, bucket) in zip(wrappers, details):
            wrapper_info = {}

            wrapper_data = data[data.wrapper == wrapper]
            if len(wrapper_data) == 0:
                continue
            token = wrapper_data.vault.iloc[-1]

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
    return metrics_to_export, start

@dask.delayed(nout=2)
async def collect_partners(partner_data: List[Tuple[List[dict], int]]):
    start = None
    metrics_to_export = []
    for partner_data, _start in partner_data:
        if start is None or _start < start:
            start = _start
        metrics_to_export.extend(partner_data)
    duration = 0 if start is None else time.time() - start
    return metrics_to_export, duration


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

def main():
    # This is forward-only
    Exporter(
        name = 'partners',
        data_query = 'partners{network="' + Network.label() + '"}',
        data_fn = export_partners,
        start_block = chain.height
    ).run("forward")
