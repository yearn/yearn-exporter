from brownie import ZERO_ADDRESS
import pytest
from yearn.prices import chainlink

assets = [
    '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
    '0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB',
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "0xdB25f211AB05b1c97D595516F45794528a807ad8",
    "0xC581b735A1688071A1746c968e0798D642EDE491",
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620",
    "0x95dFDC8161832e4fF7816aC4B6367CE201538253",
    "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "0x584bC13c7D411c00c01A62e8019472dE68768430",
    "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
    "0xc00e94Cb662C3520282E6f5717214004A7f26888",
    "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e",
]


@pytest.mark.parametrize('asset', assets)
def test_chainlink_latest(asset):
    price = chainlink.get_price(asset)
    assert price, 'no feed available'


@pytest.mark.parametrize('asset', assets)
def test_chainlink_before_registry(asset):
    price = chainlink.get_price(asset, block=12800000)
    assert price, 'no feed available'


def test_chainlink_nonexistent():
    price = chainlink.get_price(ZERO_ADDRESS)
    assert price is None


def test_chainlink_before_feed():
    # try to fetch yfi price one block before feed is deployed
    price = chainlink.get_price('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e', 12742718)
    assert price is None
