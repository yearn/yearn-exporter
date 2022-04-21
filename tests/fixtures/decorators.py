
import pytest
from brownie import chain
from yearn import ironbank
from yearn.networks import Network
from yearn.prices import aave, fixed_forex, synthetix

mainnet_only = pytest.mark.skipif(
    chain.id != Network.Mainnet,
    reason="Only applicable on Mainnet."
)

aave_chains_only = pytest.mark.skipif(
    chain.id not in aave.address_providers,
    reason='Not applicable on chains without Aave deployments.'
)

ib_chains_only = pytest.mark.skipif(
    chain.id not in ironbank.addresses,
    reason='Not applicable on chains without IronBank deployments.'
)

ff_chains_only = pytest.mark.skipif(
    chain.id not in fixed_forex.addresses,
    reason='Not applicable on chains without Fixed Forex deployments.'
)

synthetix_chains_only = pytest.mark.skipif(
    chain.id not in synthetix.addresses,
    reason='Not applicable on chains without Synthetix deployments.'
)
