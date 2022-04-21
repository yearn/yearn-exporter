
from random import randint

import pytest
from brownie import chain
from tests.fixtures.decorators import mainnet_only

from yearn.exceptions import UnsupportedNetwork
from yearn.iearn import Registry
from yearn.utils import contract_creation_block

try:
    registry = Registry()
    start_block = min(contract_creation_block(iearn.vault.address)for iearn in registry.vaults)
    blocks = [randint(start_block,chain.height) for i in range(50)]
except UnsupportedNetwork:
    pass

@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_describe_iearn(block):
    description = registry.describe(block=block)
    for iearn in registry.vaults:
        assert iearn in description
        assert description[iearn]["total supply"]
        assert description[iearn]["available balance"]
        assert description[iearn]["pooled balance"]
        assert description[iearn]["price per share"]
        assert description[iearn]["token price"]
        assert description[iearn]["tvl"]
        assert description[iearn]["address"]
        assert description[iearn]["version"]

@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at(block):
    assert registry.active_vaults_at(block=block)

@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at(block):
    assert registry.total_value_at(block=block)
