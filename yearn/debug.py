import os
import logging
logger = logging.getLogger(__name__)

class Debug(object):

    @staticmethod
    def extract_variables(variables):
      logger.info("*** DEBUG LOCAL VARIABLES ***")
      return { k: v for k, v in variables.items() if '__' not in k and 'pdb' not in k and 'self' not in k }
