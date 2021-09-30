from dataclasses import dataclass


@dataclass
class Config:
    watch_events: bool = True


config = Config()
