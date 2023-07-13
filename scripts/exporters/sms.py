
import logging

import sentry_sdk
from y.networks import Network

from yearn import constants
from yearn.helpers.exporter import Exporter
from yearn.outputs.victoria.victoria import _post
from yearn.treasury.treasury import StrategistMultisig

sentry_sdk.set_tag('script','sms_exporter')

logger = logging.getLogger('yearn.sms_exporter')

sms = StrategistMultisig(asynchronous=True)

exporter = Exporter(
    name = 'sms',
    data_query = 'sms_assets{network="' + Network.label() + '"}',
    data_fn = sms.data_for_export,
    export_fn = _post,
    start_block = sms._start_block,
    concurrency=constants.CONCURRENCY,
)

def main():
    exporter.run()
