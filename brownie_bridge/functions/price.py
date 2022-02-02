from yearn.prices import magic
from yearn.exceptions import PriceError
import logging

logger = logging.getLogger(__name__)

def get_price(address):
    price = 0
    try:
        price = magic.get_price(address)
    except (PriceError, AttributeError, ValueError) as e:
        logger.error(e)
        logger.error("Could not find price for %s", address)

    return { "address": address, "price": price, "unit": "USD" }
