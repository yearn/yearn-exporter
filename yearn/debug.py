import os
import inspect
import logging
from yearn.utils import Singleton

logger = logging.getLogger(__name__)

class Debug(metaclass=Singleton):
    def __init__(self):
        self._collected_variables = {}

    def collect_variables(self, variables):
        stack = inspect.stack()
        class_name = stack[1][0].f_locals["self"].__class__.__name__
        method_name = stack[1][0].f_code.co_name
        extracted = { k: v for k, v in variables.items() if '__' not in k and 'pdb' not in k }
        self._collected_variables[f'{class_name}#{method_name}'] = extracted
        return extracted

    def get_collected_variables(self):
        return self._collected_variables
