from yearn.prices.aave import aave

aDAI = '0x028171bCA77440897B824Ca71D1c56caC55b68A3'
DAI = '0x6B175474E89094C44Da98b954EedeAC495271d0F'


def test_aave():
    assert aDAI in aave
    assert aave.atoken_underlying(aDAI) == DAI


def test_markets():
    assert aave.markets[aDAI] == DAI
    assert len(aave.markets) > 10
