import logging
from typing import Optional, Union
from yearn.prices.balancer.v1 import BalancerV1, balancer_v1
from yearn.prices.balancer.v2 import BalancerV2, balancer_v2
from yearn.typing import Address

logger = logging.getLogger(__name__)

BALANCERS = {
  "v1": balancer_v1,
  "v2": balancer_v2
}
class BalancerSelector:
    def __init__(self) -> None:
        self.balancers = {
            version: balancer for version, balancer in BALANCERS.items() if balancer
        }


    def has_balancers(self) -> bool:
        return len(self.balancers) > 0


    def get_balancer_for_pool(self, address: Address) -> Optional[Union[BalancerV1, BalancerV2]]:
        for b in BALANCERS.values():
            if b.is_balancer_pool(address):
                return b

        return None

selector = BalancerSelector()
