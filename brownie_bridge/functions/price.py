from yearn.prices import magic
from yearn.exceptions import PriceError
from sentry_sdk import capture_exception
import logging

logger = logging.getLogger(__name__)

def get_price(address):
    price = 0
    try:
        price = magic.get_price(address)
    except (PriceError, AttributeError, ValueError) as e:
        logger.error(e)
        logger.error("Could not find price for %s", address)
    except Exception as e:
        capture_exception(e)
        logger.error(e)
        logger.error("Could not find price for %s", address)


    return { "address": address, "price": price, "unit": "USD" }
