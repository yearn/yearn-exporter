
from brownie import network

from yearn.logs import setup_logging
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()

if network.is_connected():
    # If ypm db is not yet initialized, force eth-util extended version
    import eth_portfolio._db.entities
    
    from yearn._setup import (customize_ypricemagic,
                              force_init_problematic_contracts)
    from yearn.middleware.middleware import setup_middleware
    
    setup_middleware()
    force_init_problematic_contracts()
    customize_ypricemagic()
