from yearn.logs import setup_logging
from yearn.middleware.middleware import setup_middleware
from yearn.sentry import setup_sentry

setup_logging()
setup_middleware()
setup_sentry()
