import logging
import os
import time

import sentry_sdk
from brownie import chain
from yearn.outputs.victoria import output_duration
from yearn.treasury.treasury import StrategistMultisig

sentry_sdk.set_tag('script','sms_exporter')

logger = logging.getLogger('yearn.sms_exporter')
sleep_interval = int(os.environ.get('SLEEP_SECONDS', '0'))


def main():
    treasury = StrategistMultisig(watch_events_forever=True)
    for block in chain.new_blocks(height_buffer=12):
        start_time = time.time()
        treasury.export(block.number, block.timestamp)
        duration = time.time() - start_time
        output_duration.export(duration, 1, "sms_forwards", block.timestamp)
        time.sleep(sleep_interval)
