import pytest

from yearn.prices import magic, uniswap_v3
from tests.prices.utils import tokens


@pytest.mark.parametrize('token', tokens)
def test_uniswap_v3(token):
    price = uniswap_v3.get_price(token)
    alt_price = magic.get_price(token)
    print(token, price, alt_price)
    # being within 2% difference is acceptable
    assert price == pytest.approx(alt_price, rel=2e-2)
