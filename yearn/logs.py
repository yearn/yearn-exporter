import logging
import warnings
from brownie.exceptions import BrownieEnvironmentWarning


def setup_logging():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(name)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    warnings.filterwarnings(
        'ignore',
        r".*defines a 'balance' function.*",
        BrownieEnvironmentWarning
    )
