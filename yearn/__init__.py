
from brownie import network, chain
from multicall.multicall import batcher

from yearn.logs import setup_logging
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()

if network.is_connected():
    from y import Network
    from yearn._setup import (customize_ypricemagic,
                              force_init_problematic_contracts)
    from yearn.middleware.middleware import setup_middleware
    
    # needed for base
    if chain.id == Network.Base:
        batcher.step = 2000

    setup_middleware()
    force_init_problematic_contracts()
    customize_ypricemagic()
