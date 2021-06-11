from dataclasses import dataclass

@dataclass
class Tvl:
  total_assets: int = 0
  price: float = 0
  tvl: float = 0