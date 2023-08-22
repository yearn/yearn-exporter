import os
import sys
import time
import logging
import os
import traceback

from multicall.utils import await_awaitable

logger = logging.getLogger(__name__)

def main(address):
    from yearn.apy.common import get_samples
    start = time.perf_counter()
    from yearn.v2.registry import Registry
    from yearn.v2.vaults import Vault
    registry = Registry()
    vault = Vault.from_address(address)
    vault.registry = registry
    logger.info(f'apy {str(await_awaitable(vault.apy(get_samples())))}')
    logger.info(f' ⏱️  {time.perf_counter() - start} seconds')

def with_exception_handling():
    address = os.getenv("DEBUG_ADDRESS", None)
    if not address:
      raise ValueError("no address specified via $DEBUG_ADDRESS")

    from yearn.debug import Debug
    try:
        main(address)
    except Exception as e:
        traceback.print_exc()
        logger.error(e)
    finally:
        collected_variables = Debug().get_collected_variables()
        logger.info("*** Available variables for debugging ***")
        available_variables = [ k for k in locals().keys() if '__' not in k and 'pdb' not in k and 'self' != k and 'sys' != k ]
        logger.info(available_variables)

if __name__ == '__main__':
    globals()[sys.argv[1]]()
