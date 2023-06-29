import os
import logging
import traceback

logger = logging.getLogger(__name__)

def main(address):
    from yearn.v2.registry import Registry
    from yearn.v2.vaults import Vault
    from yearn.apy.common import get_samples
    registry = Registry()
    vault = Vault.from_address(address)
    vault.registry = registry
    print(vault.apy(get_samples()))

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
