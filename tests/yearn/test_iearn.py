
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
        name = iearn.name
        if name not in description:
            assert contract_creation_block(iearn.vault.address) > block, f'iearn {iearn.name} missing from Registry().describe({block}).'
            continue

        assert description[name]["address"] == iearn.vault.address, f'Incorrect address returned for iearn {iearn.name}'

        params = "total supply", "available balance", "pooled balance", "price per share", "token price", "tvl", "version"
        for param in params:
            assert param in description[name], f'Unable to fetch {param} for iearn {iearn.name}.'


@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at(block):
    assert registry.active_vaults_at(block=block)

@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at(block):
    assert registry.total_value_at(block=block)
