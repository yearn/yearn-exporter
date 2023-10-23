import dataclasses
import logging
import re
from time import sleep, time

import requests
import sentry_sdk
from brownie import ZERO_ADDRESS, chain
from brownie.exceptions import ContractNotFound
from multicall.utils import await_awaitable
from y import Contract, Network
from y.exceptions import ContractNotVerified

from yearn.apy import Apy, ApyFees, ApyPoints, get_samples
from yearn.apy.curve.simple import Gauge, calculate_simple
from yearn.helpers import s3, telegram

logger = logging.getLogger(__name__)
sentry_sdk.set_tag('script','curve_apy_previews')

chains = {
    Network.Mainnet: 'ethereum'
}
CURVE_API_URL = "https://api.curve.fi/api/getAllGauges"


def main():
    gauges = _get_gauges()
    data = _build_data(gauges)
    s3.upload('apy-previews', 'curve-factory', data)

def _build_data(gauges):
    samples = get_samples()
    data = []
    for name, values in gauges.items():
        m = re.match('^([^\(\)]+) \(.*\)', name)
        gauge_name = m[1]
        try:
            gauge = _extract_gauge(values)
        except ContractNotVerified as e:
            data.append({
                "gauge_name": gauge_name,
                "apy": dataclasses.asdict(Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0), error_reason=str(e))),
                "updated": int(time()),
                "block": samples.now,
            })
            continue
        if not gauge:
            continue

        pool_coins = []
        for i in range(4):
            try:
                coin_address = gauge.pool.coins(i)
            except ValueError as e:
                # If the execution reverted, there is no coin with index i.
                if str(e) == "execution reverted":
                    continue
                raise

            # Sometimes the call returns the zero address instead of reverting. This means there is no coin with index i.
            if coin_address == ZERO_ADDRESS:
                continue

            try:
                if coin_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                    name = "ETH"
                else:
                    c = Contract(coin_address)
                    name = c.name()

                pool_coins.append({"name": name, "address": coin_address})
            except (ContractNotFound, ContractNotVerified, ValueError, AttributeError) as e:
                pool_coins.append({"address": coin_address, "error": str(e)})
                logger.error(f"error for coins({i}) for pool {str(gauge.pool)}")
                logger.error(e)

        apy_error = Apy("error", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
        try:
            if gauge.gauge_weight > 0:
                apy = await_awaitable(calculate_simple(None, gauge, samples))
            else:
                apy = Apy("zero_weight", 0, 0, ApyFees(0, 0), ApyPoints(0, 0, 0))
        except Exception as error:
            apy_error.error_reason = ":".join(str(arg) for arg in error.args)
            logger.error(error)
            logger.error(gauge)
            apy = apy_error

        object = {
            "gauge_name": gauge_name,
            "gauge_address": str(gauge.gauge),
            "pool_address": str(gauge.pool),
            "pool_coins": pool_coins,
            "lp_token": str(Contract(gauge.lp_token)),
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
    pool = Contract(pool_address)
    gauge = Contract(gauge_address)
    weight = int(gauge_controller["gauge_relative_weight"])
    inflation_rate = int(gauge_data["inflation_rate"])
    working_supply = int(gauge_data["working_supply"])

    return Gauge(lp_token, pool, gauge, weight, inflation_rate, working_supply)


def _get_gauges():
    if chain.id in chains:
        url = f"{CURVE_API_URL}?blockChainId={chains[chain.id]}"
        attempts = 0
        while attempts < 5:
            response = requests.get(url)
            response_json = response.json()
            if response_json["success"]:
                return response_json["data"]
            logger.error(response_json)
            if attempts >= 5:
                raise ValueError(f"Error fetching gauges from {url}")
            attempts += 1
            sleep(.1)
    else:
        raise ValueError(f"can't get curve gauges for unsupported network: {chain.id}")
    
def with_monitoring():
    telegram.run_job_with_monitoring('Curve Previews API', main)
