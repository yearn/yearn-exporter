import pytest
from brownie import ZERO_ADDRESS
from tests.prices.utils import tokens
from yearn.prices import chainlink


@pytest.mark.parametrize('token', tokens)
def test_chainlink_latest(token):
    price = chainlink.get_price(token)
    assert price, 'no feed available'


@pytest.mark.parametrize('token', tokens)
def test_chainlink_before_registry(token):
    price = chainlink.get_price(token, block=12800000)
    assert price, 'no feed available'


def test_chainlink_nonexistent():
    price = chainlink.get_price(ZERO_ADDRESS)
    assert price is None


def test_chainlink_before_feed():
    # try to fetch yfi price one block before feed is deployed
    price = chainlink.get_price('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e', 12742718)
    assert price is None
