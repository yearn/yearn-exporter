import gzip
import json
import logging
import math
import os
from decimal import Decimal
from typing import Dict, List

import aiohttp
import eth_retry
from brownie import chain
from y.networks import Network

BASE_URL = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
IMPORT_URL = f'{BASE_URL}/api/v1/import'
VM_REQUEST_HEADERS = {'Connection': 'close', 'Content-Encoding': 'gzip'}

logger = logging.getLogger(__name__)

@eth_retry.auto_retry
async def has_data(ts, data_query):
    # query for a metric which should be present
    url = f'{BASE_URL}/api/v1/query?query={data_query}&time={int(ts)}'
    headers = {
        'Connection': 'close',
    }
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                response = await session.get(
                    url = url,
                    headers = headers
                )
                result = await response.json()
                return result['status'] == 'success' and len(result['data']['result']) > 0
            except aiohttp.client_exceptions.ServerDisconnectedError:
                pass

def _build_item(metric, label_names, label_values, value, timestamp):
    ts_millis = math.floor(timestamp) * 1000
    label_names.append("network")
    label_values.append(Network.label(chain.id))
    meta = dict(zip(map(_sanitize, label_names), map(str, label_values)))
    meta["__name__"] = metric
    return {"metric": meta, "values": [_sanitize(value)], "timestamps": [ts_millis]}


def _to_jsonl_gz(metrics_to_export: List[Dict]):
    lines = []
    for item in metrics_to_export:
        lines.append(json.dumps(item))

    jsonlines = "\n".join(lines)
    return gzip.compress(bytes(jsonlines, "utf-8"))


async def _post(metrics_to_export: List[Dict]) -> None:
    """ Post all metrics at once."""
    data = _to_jsonl_gz(metrics_to_export)
    attempts = 0
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    url = IMPORT_URL,
                    headers = VM_REQUEST_HEADERS,
                    data = data,
                )
            return
        except Exception as e:
            if not isinstance(e, aiohttp.ClientError):
                raise e
            attempts += 1
            logger.debug('You had a ClientError: %s', e)
            if attempts >= 10:
                raise e

def _sanitize(value):
    if isinstance(value, bool):
        return int(value)
    elif isinstance(value, Decimal):
        # Decimal is not JSON serializable
        return float(value)
    elif isinstance(value, str):
        return value.replace('"', '')  # e.g. '"yvrenBTC" 0.3.5 0x340832'
    return value
