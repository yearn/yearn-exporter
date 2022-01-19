from yearn.logs import setup_logging
from yearn.middleware.middleware import setup_middleware

setup_logging()
try:
    setup_middleware()
except:
    # NOTE: Middleware already set up elsewhere, good stuff
    pass
