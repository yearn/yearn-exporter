import os
import logging
from pprint import pformat
logger = logging.getLogger(__name__)

class Debug(object):

    @staticmethod
    def extract_variables(variables):
      logger.info("*** DEBUG LOCAL VARIABLES ***")
      return pformat({ k: v for k, v in variables.items() if '__' not in k and 'pdb' not in k and 'self' not in k })
