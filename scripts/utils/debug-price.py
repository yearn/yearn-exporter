
import logging
import os

from brownie import chain

import y

y_logger = logging.getLogger('y')
y_logger.setLevel(logging.DEBUG)
y_logger.addHandler(logging.StreamHandler())

def main():
    BAD = os.environ.get("BAD")
    BLOCK = os.environ.get("BLOCK")
    if not BAD:
        raise ValueError("You must specify a token to debug by setting BAD env var")
    if not BLOCK:
        BLOCK = chain.height
        y_logger.warning("no BLOCK specified, using %s", BLOCK)
    y.get_price(BAD, int(BLOCK), skip_cache=True)
