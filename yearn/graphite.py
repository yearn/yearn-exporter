import logging
import os
from datetime import datetime

import requests

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("graphite.metrics")

GRAFANA_URL = os.environ.get("GRAFANA_URL")
GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY")


def send_metric(metric_name: str, value: float, time: datetime, tags=None, resolution: int = 10):
    if GRAFANA_URL is None or GRAFANA_API_KEY is None:
        return

    if not metric_name:
        raise Exception("Metric name should not be empty")

    metric_tags = []
    for key, val in tags.items():
        metric_tags.append(f"{key}={val}")

    headers = {"Authorization": "Bearer %s" % GRAFANA_API_KEY}

    grafana_data = {
        'name': metric_name,
        'metric': metric_name,
        'value': float(value),
        'interval': int(resolution),
        'unit': '',
        'time': int(time.timestamp()),
        'mtype': 'count',
        'tags': metric_tags,
    }

    result = requests.post(GRAFANA_URL, json=[grafana_data], headers=headers)
    if result.status_code != 200:
        logger.error(f"Failed to send metric {metric_name} with value {value}: {result.text}")

    logger.debug('%s: %s' % (result.status_code, result.text))
