import logging
import os
import warnings

from brownie.exceptions import (BrownieCompilerWarning,
                                BrownieEnvironmentWarning)


def setup_logging():
    logging.basicConfig(
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
