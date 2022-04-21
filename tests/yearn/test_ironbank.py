
from random import randint

import pytest
from brownie import chain
from tests.fixtures.decorators import ib_chains_only

from yearn.exceptions import UnsupportedNetwork
from yearn.ironbank import Registry
from yearn.utils import contract_creation_block

try:
    registry = Registry()
    start_block = min(
        contract_creation_block(vault.vault.address)
        for vault in registry.vaults
        # Disregard when block == 0 due to binary search issue.
        if contract_creation_block(vault.vault.address)
    )
    blocks = [randint(start_block,chain.height) for i in range(50)]
except UnsupportedNetwork:
    pass

params = [
    "total supply", "total cash", "total supplied", "total borrows", "total reserves", "exchange rate",
    "token price", "underlying price", "supply apy", "borrow apy", "utilization", "tvl", "version",
]

BUFFER = 10_000


@ib_chains_only
def test_ironbank_contract():
    assert registry.ironbank


@ib_chains_only
@pytest.mark.parametrize('block',blocks)
def test_describe_ib(block):
    description = registry.describe(block=block)
    if not description:
        assert 
    for ib in registry.vaults:
        name = ib.name
        if name not in description:
            assert ib.vault.address not in registry.ironbank.getAllMarkets(block_identifier=block), f'IronBank {ib.name} missing from Registry().describe({block}).'
            continue
        for param in params:
            assert param in description[name], f"Unable to fetch {param} for IronBank {ib.name}."
        assert description[name]["address"] == ib.vault.address, f'Incorrect address returned for IronBank {ib.name}.'


@ib_chains_only
@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at_ib(block):
    assert registry.active_vaults_at(block=block), f"Unable to fetch active ironbank deployments at block {block}."


@ib_chains_only
@pytest.mark.parametrize('block',blocks)
def test_total_value_at_ib(block):
    assert registry.total_value_at(block=block), f"Unable to fetch ironbank tvl at block {block}."
