from random import randint

import pytest
from brownie import ZERO_ADDRESS, chain
from brownie.exceptions import VirtualMachineError
from multicall.utils import await_awaitable
from y import Contract
from y.contracts import contract_creation_block

from tests.fixtures.decorators import mainnet_only
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.v1.registry import Registry
from yearn.v1.vaults import VaultV1

try:
    registry = Registry()
    vaults = registry.vaults
    start_block = min(contract_creation_block(vault.vault.address) for vault in vaults)
    blocks = [randint(start_block,chain.height) for i in range(50)]
except UnsupportedNetwork:
    registry, vaults, blocks = None, [], []

params = "vault balance", "vault total", "strategy balance", "share price"

curve_params = [
    "earned",
    # curve.calculate_boost
    "gauge balance", "gauge total", "vecrv balance", "vecrv total", "working balance", "working total", "boost", "max boost", "min vecrv",
    # curve.calculate_apy
    "crv price", "relative weight", "inflation rate", "virtual price", "crv reward rate", "crv apy", "token price",
]

@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_describe_v1(block):
    assert registry.describe(block=block)


@mainnet_only
@pytest.mark.parametrize('vault',vaults)
def test_describe_vault_v1(vault: VaultV1):
    blocks = [randint(contract_creation_block(vault.vault.address), chain.height) for i in range(25)]
    for block in blocks:
        try:
            vault.vault.getPricePerFullShare(block_identifier=block)
        except (ValueError, VirtualMachineError) as e:
            expected_errors = [
                "execution reverted",
                "revert: SafeMath: division by zero",
            ]
            if not any([str(e) == err for err in expected_errors]):
                raise
            print('Not applicable until vault has a ppfs. Skipping.')
            continue

        strategy = vault.get_strategy(block=block)
        
        if not strategy:
            controller = vault.get_controller(block=block)
            assert controller
            strategy = controller.strategies(vault.token, block_identifier=block)
            assert strategy == ZERO_ADDRESS
        
        description = vault.describe(block=block) 

        for param in params:
            if param in ["share price", "vault balance"] and param not in description:
                assert description["vault total"] == 0
            else:
                assert param in description, f'Unable to fetch {param} for vault {vault.name}'
                
        if hasattr(vault.vault, "available"):
            assert "available" in description

        if hasattr(vault.vault, "min") and hasattr(vault.vault, "max"):
            assert "min" not in description
            assert "max" not in description
            assert "strategy buffer" in description

        if await_awaitable(vault.is_curve_vault) and hasattr(strategy, "proxy"):
            vote_proxy, gauge = fetch_multicall(
                [strategy, "voter"],  # voter is static, can pin
                [strategy, "gauge"],  # gauge is static per strategy, can cache
                block=block,
            )
            if vote_proxy and gauge:
                for param in curve_params:
                    assert param in description, f'Unable to fetch {param} for vault {vault.name}'

        if hasattr(strategy, "earned"):
            assert "lifetime earned" in description
        
        if strategy._name == "StrategyYFIGovernance":
            assert "earned" in description
            assert "reward rate" in description
            assert "ygov balance" in description
            assert "ygov total" in description

        assert description["token price"]
        assert "tvl" in description


@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_active_vaults_at_v1(block):
    assert registry.active_vaults_at(block=block), f"Unable to fetch active v1 vaults at block {block}."


@mainnet_only
@pytest.mark.parametrize('block',blocks)
def test_total_value_at_v1(block):
    assert registry.total_value_at(block=block), f"Unable to fetch v1 tvl at block {block}."


@mainnet_only
def test_get_v1_strategy():
    old_block = 10532708
    vault = next(x for x in registry.vaults if x.vault == '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e')
    assert vault.get_controller(old_block) == Contract('0x31317F9A5E4cC1d231bdf07755C994015A96A37c')

    assert vault.get_strategy(old_block) is None
    assert vault.get_strategy(old_block + 100) == Contract('0x003312E3eBBe6b0f25f1c03C2695d83075d9a9B8')
    assert vault.get_strategy(old_block + 1000) == Contract('0xea061fDd1cd80176455bDb314C87d78570a8fb26')

    new_block = 10640746
    assert vault.get_controller(new_block) == vault.controller


@mainnet_only
def test_gusd_fooling_heuristic():
    # gusd vault got mistakengly treated as curve and sent to curve apy calculations
    vault = next(x for x in registry.vaults if x.name == 'GUSD')
    assert vault.get_strategy(11597690) == Contract('0xc8327D8E1094a94466e05a2CC1f10fA70a1dF119')
    assert vault.describe(11597690)


@mainnet_only
def test_is_curve_vault():
    non_curve = ['USDC', 'TUSD', 'DAI', 'USDT', 'YFI', 'WETH', 'GUSD', 'mUSD']
    for vault in registry.vaults:
        if vault.name in non_curve:
            continue
        assert await_awaitable(vault.is_curve_vault)
