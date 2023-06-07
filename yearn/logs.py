import logging
import os
import warnings

from brownie.exceptions import (BrownieCompilerWarning,
                                BrownieEnvironmentWarning)


def setup_logging():
    basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(levelname)s %(name)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    warnings.filterwarnings(
        'ignore',
        r".*defines a 'balance' function.*",
        BrownieEnvironmentWarning
    )

    warnings.filterwarnings(
        'ignore',
        r"Namespace collision between contract function and brownie `Contract` class member: *",
        BrownieEnvironmentWarning
    )

    warnings.filterwarnings(
        'ignore',
        r"0x*: Locally compiled and on-chain bytecode do not match!",
        BrownieCompilerWarning
    )

def basicConfig(**kwargs) -> None:
    """Our own version of logging.basicConfig that silences logs we aren't interested in"""
    logging.basicConfig(**kwargs)
    if kwargs.get('level', None) in [logging.DEBUG, "DEBUG"]:
        silence_logger('urllib3.connectionpool') # async provider uses aiohttp
        silence_logger('y.utils.middleware') # this is only applied to sync web3 instance
        silence_logger('web3.providers.HTTPProvider') # we use AsyncHTTPProvider
        silence_logger('web3.RequestManager') # not really sure lol
        silence_logger('dank_mids.should_batch') # this is only really useful when optimizing dank_mids internals
        
def silence_logger(name: str):
    logging.getLogger(name).setLevel(logging.CRITICAL)