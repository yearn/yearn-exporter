import pytest
from tests.fixtures.decorators import mainnet_only
from yearn.prices.synthetix import synthetix
from yearn.utils import contract

SYNTHS = []
if synthetix:
    SYNTHS = synthetix.synths


@mainnet_only
def test_get_synths():
    assert len(synthetix.synths) >= 10


@mainnet_only
def test_synthetix_detection():
    sLINK = '0xbBC455cb4F1B9e4bFC4B73970d360c8f032EfEE6'
    assert sLINK in synthetix


@mainnet_only
@pytest.mark.parametrize('target', SYNTHS)
def test_synthetix_price(target):
    token = contract(target).proxy()
    price = synthetix.get_price(token)
    print(price, contract(target).currencyKey().decode().rstrip('\x00'))
    return price
