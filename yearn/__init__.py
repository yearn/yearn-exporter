
from brownie import network, chain, web3
from web3.middleware.geth_poa import geth_poa_middleware

from yearn.logs import setup_logging
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()

if network.is_connected():
    # If ypm db is not yet initialized, force eth-util extended version
    import eth_portfolio._db.entities
    
    from y import Network
    from yearn._setup import (customize_ypricemagic,
                              force_init_problematic_contracts)
    from yearn.middleware.middleware import setup_middleware
    
    # needed for base and opti
    
    if chain.id == Network.Optimism:
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    setup_middleware()
    force_init_problematic_contracts()
    customize_ypricemagic()
