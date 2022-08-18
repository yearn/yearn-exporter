from brownie import network
from yearn.logs import setup_logging
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()

if network.is_connected():
    from yearn.middleware.middleware import setup_middleware
    setup_middleware()
