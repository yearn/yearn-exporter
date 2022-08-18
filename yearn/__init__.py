from brownie import network
from yearn.logs import setup_logging
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()
# hacky workaround when node doesn't support web3_clientVersion
try:
    if network.is_connected():
        from yearn.middleware.middleware import setup_middleware
        setup_middleware()
except AssertionError:
    from yearn.middleware.middleware import setup_middleware
    setup_middleware()
