import gzip
import json
import logging
import math
import os
from decimal import Decimal
from typing import Dict, List, Tuple

import eth_retry
from aiohttp import ClientError, ClientSession, ServerDisconnectedError
from msgspec import Raw, Struct
from msgspec.json import decode
from y import Network
from y.constants import CHAINID

BASE_URL = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
IMPORT_URL = f'{BASE_URL}/api/v1/import'
VM_HAS_DATA_HEADERS = {'Connection': 'close'}
VM_POST_HEADERS = {'Connection': 'close', 'Content-Encoding': 'gzip'}
NETWORK_LABEL = Network.label(CHAINID)

logger = logging.getLogger(__name__)

# These 2 helpers enable us to decode only the relevant
# data in the json response and discard the rest
class Data(Struct):
    result: Tuple[Raw, ...]

class Response(Struct):
    status: str
    data: Data

@eth_retry.auto_retry
async def has_data(ts: float, data_query: str) -> bool:
    # sourcery skip: use-contextlib-suppress
    # query for a metric which should be present
    # TODO: update this so it only checks data exists, doesnt need to return data
    url = f'{BASE_URL}/api/v1/query?query={data_query}&time={int(ts)}'
    async with ClientSession() as session:
        while True:
            try:
                response = await session.get(url = url, headers = VM_HAS_DATA_HEADERS)
                result = decode(await response.read(), type=Response)
                return result.status == 'success' and len(result.data.result) > 0
            except ServerDisconnectedError:
                pass

def _build_item(metric, label_names, label_values, value, timestamp):
    ts_millis = math.floor(timestamp) * 1000
    return {
        "metric": dict(
            zip(map(_sanitize_name, label_names), map(str, label_values)), 
            network=NETWORK_LABEL, 
            __name__=metric,
        ), 
        "values": [_sanitize(value)], 
        "timestamps": [ts_millis],
    }


def _to_jsonl_gz(metrics_to_export: List[Dict]):
    lines = map(json.dumps, metrics_to_export)
    jsonlines = "\n".join(lines)
    return gzip.compress(bytes(jsonlines, "utf-8"))


async def _post(metrics_to_export: List[Dict]) -> None:
    """ Post all metrics at once."""
    data = _to_jsonl_gz(metrics_to_export)
    attempts = 0
    while True:
        try:
            async with ClientSession() as session:
                await session.post(
                    url = IMPORT_URL,
                    headers = VM_POST_HEADERS,
                    data = data,
                )
            return
        except Exception as e:
            if not isinstance(e, ClientError):
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


__sanitized_names = {}

def _sanitize_name(name: str) -> str:
    sanitized = __sanitized_names.get(name)
    if sanitized is None:
        sanitized = __sanitized_names[name] = _sanitize(name)
    return sanitized