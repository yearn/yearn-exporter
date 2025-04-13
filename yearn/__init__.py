
from brownie import network
from multicall.multicall import batcher
from y.constants import CHAINID

from yearn.logs import setup_logging

# must be called before importing sentry
setup_logging()

from yearn.sentry import setup_sentry

setup_sentry()

if network.is_connected():
    from y import Network
    from yearn._setup import (customize_ypricemagic,
                              force_init_problematic_contracts)
    from yearn.middleware.middleware import setup_middleware
    
    # needed for base
    if CHAINID == Network.Base:
        batcher.step = 2000

    setup_middleware()
    force_init_problematic_contracts()
    customize_ypricemagic()
