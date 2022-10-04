import os
import logging
from inspect import getframeinfo, stack
from yearn.utils import Singleton

logger = logging.getLogger(__name__)

class Debug(metaclass=Singleton):
    def __init__(self):
        self._collected_variables = {}

    def collect_variables(self, variables):
        caller = stack()[1][0]
        caller_frame = getframeinfo(caller)
        if "self" in caller.f_locals:
            class_name = caller.f_locals["self"].__class__.__name__
        else:
            class_name = caller_frame.filename.split("/")[-1]
        method_name = caller.f_code.co_name
        line_number = caller_frame.lineno
        extracted = { k: v for k, v in variables.items() if '__' not in k and 'pdb' not in k }
        self._collected_variables[f'{class_name}#{method_name}:{line_number}'] = extracted
        return extracted

    def get_collected_variables(self):
        return self._collected_variables
