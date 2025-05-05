
import pytest
from y.constants import CHAINID
from y.networks import Network

from yearn import ironbank
from yearn.prices import aave, fixed_forex
from yearn.prices.uniswap import v3

mainnet_only = pytest.mark.skipif(
    CHAINID != Network.Mainnet,
    reason="Only applicable on Mainnet."
)

aave_chains_only = pytest.mark.skipif(
    CHAINID not in aave.address_providers,
    reason='Not applicable on chains without an Aave deployment.'
)

ib_chains_only = pytest.mark.skipif(
    CHAINID not in ironbank.addresses,
    reason='Not applicable on chains without IronBank deployments.'
)

ff_chains_only = pytest.mark.skipif(
    CHAINID not in fixed_forex.addresses,
    reason='Not applicable on chains without a Fixed Forex deployment.'
)

uni_v3_chains_only = pytest.mark.skipif(
    CHAINID not in v3.addresses,
    reason='Not applicable on chains without a Uniswap V3 deployment.'
)
