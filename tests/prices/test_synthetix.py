import pytest
from brownie import chain
from y.networks import Network

from tests.fixtures.decorators import mainnet_only, synthetix_chains_only
from yearn.prices.synthetix import synthetix
from yearn.utils import contract

SYNTHS = []
if synthetix:
    SYNTHS = synthetix.synths


@synthetix_chains_only
def test_get_synths():
    assert len(synthetix.synths) >= {
        Network.Mainnet: 10,
        Network.Optimism: 5,
    }[chain.id]


@mainnet_only
def test_synthetix_detection():
    sLINK = '0xbBC455cb4F1B9e4bFC4B73970d360c8f032EfEE6'
    assert sLINK in synthetix


@synthetix_chains_only
@pytest.mark.parametrize('target', SYNTHS)
def test_synthetix_price(target):
    token = contract(target).proxy()
    price = synthetix.get_price(token)
    print(price, contract(target).currencyKey().decode().rstrip('\x00'))
    return price
