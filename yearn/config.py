from yearn.utils import Singleton

class Config(metaclass=Singleton):
    def __init__(self):
        self.with_events = True

    def has_events(self):
        return self.with_events
