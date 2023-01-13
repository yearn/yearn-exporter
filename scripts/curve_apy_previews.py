import requests
import dataclasses
import logging
import json
import re
import os
import boto3
import shutil
import sentry_sdk
from time import time
from brownie import chain
from yearn.apy.curve.simple import Gauge, calculate_simple
from yearn.apy import Apy, ApyFees, ApyPoints, ApySamples, get_samples
from yearn.exceptions import EmptyS3Export, PriceError
from yearn.utils import contract
from yearn.networks import Network

logger = logging.getLogger(__name__)
sentry_sdk.set_tag('script','curve_apy_previews')

chains = {
    Network.Mainnet: 'ethereum'
}
CURVE_API_URL = "https://api.curve.fi/api/getAllGauges"


def main():
    gauges = _get_gauges()
    data = _build_data(gauges)
    _upload(data)

def _build_data(gauges):
    samples = get_samples()
    data = []
    for name, values in gauges.items():
        m = re.match('^([^\(\)]+) \(.*\)', name)
        gauge_name = m[1]
        gauge = _extract_gauge(values)
        if not gauge:
            continue

        pool_coins = []
        for i in range(2):
            coin_address = gauge.pool.coins(i)
            try:
                c = contract(coin_address)
                pool_coins.append({"name": c.name(), "address": str(c)})
            except (ValueError, AttributeError) as e:
                pool_coins.append({"address": coin_address, "error": str(e)})
                logger.error(f"error for coins({i}) for pool {str(gauge.pool)}")
                logger.error(e)

        apy_error = Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
        try:
            if gauge.gauge_weight > 0:
                apy = calculate_simple(None, gauge, samples)
            else:
                apy = Apy("zero_weight", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
        except Exception as error:
            logger.error(error)
            logger.error(gauge)
            apy = apy_error

        object = {
            "gauge_name": gauge_name,
            "gauge_address": str(gauge.gauge),
            "pool_address": str(gauge.pool),
            "pool_coins": pool_coins,
            "lp_token": str(contract(gauge.lp_token)),
            "weight": str(gauge.gauge_weight),
            "inflation_rate": str(gauge.gauge_inflation_rate),
            "working_supply": str(gauge.gauge_working_supply),
            "apy": dataclasses.asdict(apy),
            "updated": int(time()),
            "block": samples.now,
        }
        data.append(object)
    return data

def _extract_gauge(v):
    if v["side_chain"] or v["is_killed"]:
        return None

    pool_address = v["swap"]
    gauge_address = v["gauge"]
    gauge_data = v["gauge_data"]
    gauge_controller = v["gauge_controller"]

    lp_token = v["swap_token"]
    pool = contract(pool_address)
    gauge = contract(gauge_address)
    weight = int(gauge_controller["gauge_relative_weight"])
    inflation_rate = int(gauge_data["inflation_rate"])
    working_supply = int(gauge_data["working_supply"])

    return Gauge(lp_token, pool, gauge, weight, inflation_rate, working_supply)


def _get_gauges():
    if chain.id in chains:
        url = f"{CURVE_API_URL}?blockChainId={chains[chain.id]}"
        response = requests.get(url)
        response_json = response.json()
        if not response_json["success"]:
            logger.error(response_json)
            raise ValueError(f"Error fetching gauges from {url}")

        return response_json["data"]
    else:
        raise ValueError(f"can't get curve gauges for unsupported network: {chain.id}")


def _upload(data):
    print(json.dumps(data, sort_keys=True, indent=4))

    file_name, s3_path = _get_export_paths("curve-factory")
    with open(file_name, "w+") as f:
        json.dump(data, f)

    if os.getenv("DEBUG", None):
        return

    aws_bucket = os.environ.get("AWS_BUCKET")

    s3 = _get_s3()
    s3.upload_file(
        file_name,
        aws_bucket,
        s3_path,
        ExtraArgs={'ContentType': "application/json", 'CacheControl': "max-age=1800"},
    )


def _get_s3():
    aws_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret = os.environ.get("AWS_ACCESS_SECRET")

    kwargs = {}
    if aws_key is not None:
        kwargs["aws_access_key_id"] = aws_key
    if aws_secret is not None:
        kwargs["aws_secret_access_key"] = aws_secret

    return boto3.client("s3", **kwargs)


def _get_export_paths(suffix):
    out = "generated"
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    api_path = os.path.join("v1", "chains", f"{chain.id}", "apy-previews")

    file_base_path = os.path.join(out, api_path)
    os.makedirs(file_base_path, exist_ok=True)

    file_name = os.path.join(file_base_path, suffix)
    s3_path = os.path.join(api_path, suffix)
    return file_name, s3_path
