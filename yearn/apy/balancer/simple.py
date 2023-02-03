import logging
from dataclasses import dataclass
from brownie import ZERO_ADDRESS, chain, interface, Contract
from yearn.typing import Address
from yearn.apy.common import (SECONDS_PER_YEAR, Apy, ApyError, ApyFees,
                                ApySamples, SharePricePoint, calculate_roi)
from yearn.networks import Network
from yearn.prices.balancer.balancer import selector as balancer_selector


logger = logging.getLogger(__name__)

def simple(vault, samples: ApySamples) -> Apy:
    if chain.id != Network.Mainnet:
        raise ApyError("bal", "chain not supported")

    lp_token = vault.token.address
    logger.info(lp_token, samples)

    # balancer = balancer_selector.get_balancer_for_pool(lp_token)

