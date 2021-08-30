import pytest
from yearn.prices import uniswap_v3

tokens = [
    '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
    '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
    '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
    '0xdAC17F958D2ee523a2206206994597C13D831ec7',
    '0x6B175474E89094C44Da98b954EedeAC495271d0F',
    '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',
    '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e',
]


@pytest.mark.parametrize('asset', tokens)
def test_uniswap_v3(asset):
    price = uniswap_v3.get_price(asset)
    print(asset, price)
    assert price, 'failed to fetch price'
