import pytest
from yearn.prices import synthetix
from yearn.utils import contract

SYNTHS = synthetix.get_synths()


def test_get_synths():
    synths = synthetix.get_synths()
    print(synths)
    assert synths


def test_synthetix_detection():
    sLINK = '0xbBC455cb4F1B9e4bFC4B73970d360c8f032EfEE6'
    assert synthetix.is_synth(sLINK)


@pytest.mark.parametrize('target', SYNTHS)
def test_synthetix_price(target):
    token = contract(target).proxy()
    price = synthetix.get_price(token)
    print(price, contract(target).currencyKey().decode().rstrip('\x00'))
    return price
