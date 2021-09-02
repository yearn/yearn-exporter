import pytest
from yearn.prices import fixed_forex

MARKETS = [
    "0xFAFdF0C4c1CB09d430Bf88c75D88BB46DAe09967",
    "0x1CC481cE2BD2EC7Bf67d1Be64d4878b16078F309",
    "0x69681f8fde45345C3870BCD5eaf4A05a60E7D227",
    "0x5555f75e3d5278082200Fb451D1b6bA946D8e13b",
    "0x96E61422b6A9bA0e068B6c5ADd4fFaBC6a4aae27",
    "0x95dFDC8161832e4fF7816aC4B6367CE201538253",
]
REGISTRY_DEPLOY_BLOCK = 13145626

@pytest.mark.parametrize('token', MARKETS)
def test_is_fixed_forex(token):
    assert fixed_forex.is_fixed_forex(token)


@pytest.mark.parametrize('token', MARKETS)
def test_fixed_forex_price(token):
    price = fixed_forex.get_price(token)
    print(price)
    assert price


@pytest.mark.parametrize('token', MARKETS)
def test_fixed_forex_price_historical(token):
    price = fixed_forex.get_price(token, block=REGISTRY_DEPLOY_BLOCK - 1)
    print(price)
    assert price
