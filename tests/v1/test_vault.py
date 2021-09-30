from brownie import Contract
from yearn.v1.registry import Registry

def test_get_v1_strategy():
    registry = Registry()
    old_block = 10532708
    vault = next(x for x in registry.vaults if x.vault == '0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e')
    assert vault.get_controller(old_block) == Contract('0x31317F9A5E4cC1d231bdf07755C994015A96A37c')

    assert vault.get_strategy(old_block) is None
    assert vault.get_strategy(old_block + 100) == Contract('0x003312E3eBBe6b0f25f1c03C2695d83075d9a9B8')
    assert vault.get_strategy(old_block + 1000) == Contract('0xea061fDd1cd80176455bDb314C87d78570a8fb26')

    new_block = 10640746
    assert vault.get_controller(new_block) == vault.controller
