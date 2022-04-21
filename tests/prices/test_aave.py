from brownie import chain
from tests.fixtures.decorators import aave_chains_only
from yearn.networks import Network
from yearn.prices.aave import aave

aDAI = {
    Network.Mainnet: '0x028171bCA77440897B824Ca71D1c56caC55b68A3',
}.get(chain.id, None)

DAI = {
    Network.Mainnet: '0x6B175474E89094C44Da98b954EedeAC495271d0F',
}.get(chain.id, None)

MIN_CT_MARKETS = {
    Network.Mainnet: 10,
}.get(chain.id, None)


@aave_chains_only
def test_aave():
    assert aDAI in aave
    assert aave.atoken_underlying(aDAI) == DAI


@aave_chains_only
def test_markets():
    assert aave.markets[aDAI] == DAI
    assert len(aave.markets) > MIN_CT_MARKETS
