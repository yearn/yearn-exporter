import pytest
from brownie import Contract, chain
from yearn.networks import Network
from yearn.v1.registry import Registry

registry = None
if chain.id == Network.Mainnet:
    registry = Registry()


@pytest.mark.require_network('mainnet')
def test_get_v1_strategy():
    old_block = 10532708
    vault = next(x for x in registry.vaults if x.vault == '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e')
    assert vault.get_controller(old_block) == Contract('0x31317F9A5E4cC1d231bdf07755C994015A96A37c')

    assert vault.get_strategy(old_block) is None
    assert vault.get_strategy(old_block + 100) == Contract('0x003312E3eBBe6b0f25f1c03C2695d83075d9a9B8')
    assert vault.get_strategy(old_block + 1000) == Contract('0xea061fDd1cd80176455bDb314C87d78570a8fb26')

    new_block = 10640746
    assert vault.get_controller(new_block) == vault.controller


@pytest.mark.require_network('mainnet')
def test_gusd_fooling_heuristic():
    # gusd vault got mistakengly treated as curve and sent to curve apy calculations
    vault = next(x for x in registry.vaults if x.name == 'GUSD')
    assert vault.get_strategy(11597690) == Contract('0xc8327D8E1094a94466e05a2CC1f10fA70a1dF119')
    assert vault.describe(11597690)


@pytest.mark.require_network('mainnet')
def test_is_curve_vault():
    non_curve = ['USDC', 'TUSD', 'DAI', 'USDT', 'YFI', 'WETH', 'GUSD', 'mUSD']
    for vault in registry.vaults:
        if vault.name in non_curve:
            continue
        assert vault.is_curve_vault
