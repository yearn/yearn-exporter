import os
import sys
import time
import logging
import traceback

logger = logging.getLogger(__name__)

def main(address):
    start = time.perf_counter()
    from yearn.v2.vaults import Vault
    from yearn.apy.common import get_samples
    vault = Vault.from_address(address)
    apy = vault.apy(get_samples())
    logger.info(f'apy {str(apy)}')
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
