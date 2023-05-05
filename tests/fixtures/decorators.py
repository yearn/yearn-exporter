
import pytest
from brownie import chain
from y.networks import Network

from yearn import ironbank
from yearn.prices import aave, fixed_forex, synthetix
from yearn.prices.uniswap import v3

mainnet_only = pytest.mark.skipif(
    chain.id != Network.Mainnet,
    reason="Only applicable on Mainnet."
)

aave_chains_only = pytest.mark.skipif(
    chain.id not in aave.address_providers,
    reason='Not applicable on chains without an Aave deployment.'
)

ib_chains_only = pytest.mark.skipif(
    chain.id not in ironbank.addresses,
    reason='Not applicable on chains without IronBank deployments.'
)

ff_chains_only = pytest.mark.skipif(
    chain.id not in fixed_forex.addresses,
    reason='Not applicable on chains without a Fixed Forex deployment.'
)

synthetix_chains_only = pytest.mark.skipif(
    chain.id not in synthetix.addresses,
    reason='Not applicable on chains without a Synthetix deployment.'
)

uni_v3_chains_only = pytest.mark.skipif(
    chain.id not in v3.addresses,
    reason='Not applicable on chains without a Uniswap V3 deployment.'
)
