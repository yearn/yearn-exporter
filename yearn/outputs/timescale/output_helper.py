import requests
import os
import gzip
import math
import json
from typing import List, Dict
from brownie import chain
from yearn.utils import contract
from yearn.networks import Network

mapping = {
    "earn": {
        "metric": "iearn",
        "labels": ["vault", "param", "address", "version"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "ib": {
        "metric": "ironbank",
        "labels": ["vault", "param", "address", "version"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "v1": {
        "metric": "yearn",
        "labels": ["vault", "param", "address", "version"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "v2": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "experimental"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "v2_strategy": {
        "metric": "yearn_strategy",
        "labels": ["vault", "strategy", "param", "address", "version", "experimental"],
    },
    "special": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "experimental"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    }
}

def _build_item(metric, label_names, label_values, value, timestamp):
    ts_millis = math.floor(timestamp) * 1000
    label_names.append("network")
    label_values.append(Network.label(chain.id))
    meta = dict(zip(map(_sanitize, label_names), map(str, label_values)))
    meta["__name__"] = metric
    return {"labels": meta, "samples": [[ts_millis, _sanitize(value)]]}



def _to_jsonl_gz(metrics_to_export: List[Dict]):
    lines = []
    for item in metrics_to_export:
        lines.append(json.dumps(item))

    jsonlines = "\n".join(lines)
    return gzip.compress(bytes(jsonlines, "utf-8"))


def _post(metrics_to_export: List[Dict]):
    base_url = os.environ.get('PROMSCALE_URL', 'http://promscale:9201')
    url = f'{base_url}/write'
    headers = {
        'Content-Type': 'application/json'
    }
    metrics_new = [json.dumps(metric) for metric in metrics_to_export]
    with requests.Session() as session:
        r = session.post(
            url = url,
            data = "".join(metrics_new),
            headers = headers
        )


def _sanitize(value):
    if isinstance(value, bool):
        return int(value)
    elif isinstance(value, str):
        return value.replace('"', '')  # e.g. '"yvrenBTC" 0.3.5 0x340832'
    
    return value


def _flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in _flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())


def _get_label_values(params, inital_labels, experimental = False):
    address = _get_string_label(params, "address")
    version = _get_string_label(params, "version")
    label_values = inital_labels + [address, version]
    if experimental:
        experimental_label = _get_bool_label(params, "experimental")
        label_values.append(experimental_label)

    return label_values


def _get_bool_label(a_dict, key):
    return "true" if key in a_dict and a_dict[key] == True else "false"


def _get_string_label(a_dict, key):
    return str(a_dict[key]) if key in a_dict else "n/a"
