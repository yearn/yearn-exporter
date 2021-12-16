import pytest
from yearn.prices.synthetix import synthetix
from yearn.utils import contract

SYNTHS = []
if synthetix:
    SYNTHS = synthetix.synths


@pytest.mark.require_network('mainnet')
def test_get_synths():
    assert len(synthetix.synths) >= 10


@pytest.mark.require_network('mainnet')
def test_synthetix_detection():
    sLINK = '0xbBC455cb4F1B9e4bFC4B73970d360c8f032EfEE6'
    assert sLINK in synthetix


@pytest.mark.require_network('mainnet')
@pytest.mark.parametrize('target', SYNTHS)
def test_synthetix_price(target):
    token = contract(target).proxy()
    price = synthetix.get_price(token)
    print(price, contract(target).currencyKey().decode().rstrip('\x00'))
    return price
