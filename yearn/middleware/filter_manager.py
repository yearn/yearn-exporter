from yearn.utils import Singleton
import itertools
from eth_utils import to_hex

class FilterManager(metaclass=Singleton):
    def __init__(self):
        self.filters = {}
        self.filter_id_counter = map(to_hex, itertools.count())

    def next_filter_id(self):
        return next(self.filter_id_counter)

    def add_filter(self, filter_id, _filter):
        self.filters[filter_id] = _filter

    def get_filter(self, filter_id):
        if filter_id not in self.filters:
            return None
        else:
            return self.filters[filter_id]
