from random import randint
from brownie import chain
import pytest
from yearn.multicall2 import fetch_multicall
from yearn.utils import contract_creation_block
from yearn.v2.registry import Registry
from yearn.v2.vaults import Vault

registry = Registry()
start_block = start_block = min(contract_creation_block(vault.vault.address)for vault in registry.vaults)
blocks = [randint(start_block,chain.height) for i in range(50)]


@pytest.mark.parametrize('block',blocks)
def test_describe_v2(block):
    assert registry.describe(block=block)


@pytest.mark.parametrize('vault',registry.vaults)
def test_describe_vault_v2(vault: Vault):
    blocks = [randint(contract_creation_block(vault.vault.address), chain.height) for i in range(25)]
    for block in blocks:
        description = vault.describe(block=block) 
        assert vault._views
        for view in vault._views:
            assert description[view]
        assert description["token price"]
        if 'totalAssets' in description:
            assert description["tvl"]
        
        assert description["experimental"]
        assert description["address"] == vault.vault.address
        assert description["version"] == "v2"

        assert description["strategies"]

        for strategy in description["strategies"]:
            assert strategy._views
            for view in strategy._views:
                assert description["strategies"][strategy][view]


def test_active_vaults_at_v2_current():
    assert registry.active_vaults_at() >= 91


@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at_v2(block):
    assert registry.active_vaults_at(block=block)


@pytest.mark.parametrize('block',blocks)
def test_total_value_at_v2(block):
    assert registry.total_value_at(block)