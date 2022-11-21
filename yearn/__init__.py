
import os

import nest_asyncio
from brownie import network, project

from yearn.logs import setup_logging

setup_logging()

nest_asyncio.apply()

if not network.is_connected() and (brownie_network := os.environ.get("BROWNIE_NETWORK")):
    # If brownie is not connected but there is a `BROWNIE_NETWORK` value, you're most likely inside of a dask worker.
    # Even if you're not, you probably still want to connect.
    network.connect(brownie_network)

    

if not project.get_loaded_projects():
    # If you're in this repo, you probably want the proect loaded. You're also likely runn===
    proj = project.load('.')
    proj._add_to_main_namespace()

if network.is_connected():
    from yearn.sentry import setup_sentry

    setup_sentry() # NOTE: Get sentry running as soon as possible.

    from yearn._setup import (customize_ypricemagic,
                              force_init_problematic_contracts)
    from yearn.middleware.middleware import setup_middleware

    setup_middleware()
    force_init_problematic_contracts()
    customize_ypricemagic()
