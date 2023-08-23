import logging
from datetime import datetime

import sentry_sdk

from yearn.partners.partners import partners
from yearn.partners.snapshot import process_partners

sentry_sdk.set_tag('script','partners_summary')

logger = logging.getLogger(__name__)

def main():
    start = datetime.now()
    process_partners(partners)
    logger.info(f"Partners summary completed in {datetime.now() - start}")
