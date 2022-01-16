import requests
import os
import gzip
import math
import json
from typing import List, Dict
from brownie import Contract, chain
from yearn.treasury.buckets import get_token_bucket
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


def export(timestamp, data):
    metrics_to_export = []

    if Network(chain.id) == Network.Fantom:
        simple_products = ["ib"]
    else:
        simple_products = ["v1", "earn", "ib", "special"]

    for product in simple_products:
        metric = mapping[product]["metric"]
        for vault, params in data[product].items():

            for key, value in params.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                has_experiments = product == "special"

                label_values = _get_label_values(params, [vault, key], has_experiments)
                label_names = mapping[product]["labels"]

                item = _build_item(metric, label_names, label_values, value, timestamp)
                metrics_to_export.append(item)


    for vault, params in data["v2"].items():
        metric = mapping["v2"]["metric"]
        for key, value in params.items():
            if key in ["address", "version", "experimental", "strategies"] or value is None:
                continue

            label_values = _get_label_values(params, [vault, key], True)
            label_names = mapping["v2"]["labels"]

            item = _build_item(metric, label_names, label_values, value, timestamp)
            metrics_to_export.append(item)

        # strategies can have nested structs
        metric = mapping["v2_strategy"]["metric"]
        for strategy, strategy_params in data["v2"][vault]["strategies"].items():
            flat = flatten_dict(strategy_params)
            for key, value in flat.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                label_values = _get_label_values(params, [vault, strategy, key], True)
                label_names = mapping["v2_strategy"]["labels"]

                item = _build_item(metric, label_names, label_values, value or 0, timestamp)
                metrics_to_export.append(item)

    # post all metrics for this timestamp at once
    _post(metrics_to_export)

def export_wallets(timestamp, data):
    metrics_to_export = []
    for key, value in data['agg_stats'].items():
        if key == 'wallet balances usd':
            for wallet, usd_bal in value.items():
                label_names = ["param","wallet"]
                label_values = ["balance usd",wallet]
                item = _build_item("aggregate", label_names, label_values, usd_bal, timestamp)
                metrics_to_export.append(item)
            continue
        label_names = ['param']
        label_values = [key]
        item = _build_item("aggregate", label_names, label_values, value, timestamp)
        metrics_to_export.append(item)
    for product in ['v1','v2']:
        metric = mapping[product]["metric"]
        for key, value in data[product].items():
            if key in mapping[product]["agg_stats"]:
                label_names = ['param']
                label_values = [key]
                item = _build_item(metric, label_names, label_values, value, timestamp)
                metrics_to_export.append(item)
                continue
            elif key == "wallet balances usd":
                for wallet, usd_bal in value.items():
                    label_names = ["param","wallet"]
                    label_values = ["balance usd",wallet]
                    item = _build_item(metric, label_names, label_values, usd_bal, timestamp)
                    metrics_to_export.append(item)
                continue
            
            vault, params = key, value
            for k, v in params.items():
                if k == 'wallet balances':
                    for wallet, bals in v.items():
                        for denom, bal in bals.items():
                            label_values = [wallet] + _get_label_values(params, [vault, denom], product in ['v2','special'])
                            label_names = ["wallet"] + mapping[product]["labels"]
                            item = _build_item(metric, label_names, label_values, bal, timestamp)
                            metrics_to_export.append(item)
                    continue

                label_values = _get_label_values(params, [vault, k], True)
                label_names = mapping[product]["labels"]

                item = _build_item(metric, label_names, label_values, v, timestamp)
                metrics_to_export.append(item)

    # post all wallet metrics for this timestamp at once
    _post(metrics_to_export)


def export_wallets(timestamp, data):
    metrics_to_export = []
    for key, value in data['agg_stats'].items():
        if key == 'wallet balances usd':
            for wallet, usd_bal in value.items():
                label_names = ["param","wallet"]
                label_values = ["balance usd",wallet]
                item = _build_item("aggregate", label_names, label_values, usd_bal, timestamp)
                metrics_to_export.append(item)
            continue
        label_names = ['param']
        label_values = [key]
        item = _build_item("aggregate", label_names, label_values, value, timestamp)
        metrics_to_export.append(item)
    for product in ['v1','v2']:
        metric = mapping[product]["metric"]
        for key, value in data[product].items():
            if key in mapping[product]["agg_stats"]:
                label_names = ['param']
                label_values = [key]
                item = _build_item(metric, label_names, label_values, value, timestamp)
                metrics_to_export.append(item)
                continue
            elif key == "wallet balances usd":
                for wallet, usd_bal in value.items():
                    label_names = ["param","wallet"]
                    label_values = ["balance usd",wallet]
                    item = _build_item(metric, label_names, label_values, usd_bal, timestamp)
                    metrics_to_export.append(item)
                continue
            
            vault, params = key, value
            for k, v in params.items():
                if k == 'wallet balances':
                    for wallet, bals in v.items():
                        for denom, bal in bals.items():
                            label_values = [wallet] + _get_label_values(params, [vault, denom], product in ['v2','special'])
                            label_names = ["wallet"] + mapping[product]["labels"]
                            item = _build_item(metric, label_names, label_values, bal, timestamp)
                            metrics_to_export.append(item)
                    continue

                label_values = _get_label_values(params, [vault, k], True)
                label_names = mapping[product]["labels"]

                item = _build_item(metric, label_names, label_values, v, timestamp)
                metrics_to_export.append(item)

    # post all wallet metrics for this timestamp at once
    _post(metrics_to_export)

def export_treasury(timestamp, data):
    metrics_to_export = []
    for section, section_data in data.items():
        for wallet, wallet_data in section_data.items():
            for token, bals in wallet_data.items():
                symbol = 'ETH' if token == 'ETH' else contract(token).symbol()
                for key, value in bals.items():
                    if value != 0:
                        label_names = ['param','wallet','token_address','token','bucket']
                        label_values = [key,wallet,token,symbol,get_token_bucket(token)]
                        item = _build_item(f"treasury_{section}",label_names,label_values,value,timestamp)
                        metrics_to_export.append(item)
    
    # post all metrics for this timestamp at once
    _post(metrics_to_export)


def export_duration(duration_seconds, pool_size, direction, timestamp_seconds):
    item = _build_item(
      "export_duration",
      [ "pool_size", "direction" ],
      [ pool_size, direction ],
      duration_seconds,
      timestamp_seconds
    )
    _post([item])


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


def _post(metrics_to_export: List[Dict]):
    data = _to_jsonl_gz(metrics_to_export)
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    url = f'{base_url}/api/v1/import'
    headers = {
        'Connection': 'close',
        'Content-Encoding': 'gzip'
    }
    with requests.Session() as session:
        session.post(
            url = url,
            data = data,
            headers = headers
        )


def _sanitize(value):
    if isinstance(value, bool):
        return int(value)
    elif isinstance(value, str):
        return value.replace('"', '')  # e.g. '"yvrenBTC" 0.3.5 0x340832'
    
    return value


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
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
