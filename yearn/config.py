from dataclasses import dataclass


@dataclass
class Config:
    watch_events_forever: bool = True


config = Config()
