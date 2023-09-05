from unittest.mock import MagicMock

import pytest
from multicall.utils import await_awaitable

from yearn.apy.curve.simple import _ConvexVault
from yearn.v2.vaults import Vault as VaultV2


@pytest.fixture
def v2_vault():
    return MagicMock(spec=VaultV2)

@pytest.fixture
def convex_strategy():
    strategy = MagicMock()
    strategy.name = "convexTestStrat"
    return strategy

@pytest.fixture
def non_convex_strategy():
    strategy = MagicMock()
    strategy.name = "yetAnotherTestStrat"
    return strategy

def test_is_convex_vault(v2_vault, convex_strategy):
    v2_vault.strategies = [convex_strategy]
    assert await_awaitable(_ConvexVault.is_convex_vault(v2_vault)) == True

def test_is_not_convex_vault(v2_vault, non_convex_strategy):
    v2_vault.strategies = [non_convex_strategy]
    assert await_awaitable(_ConvexVault.is_convex_vault(v2_vault)) == False

def test_is_convex_strategy(convex_strategy):
    assert _ConvexVault.is_convex_strategy(convex_strategy) == True

def test_is_non_convex_strategy(non_convex_strategy):
    assert _ConvexVault.is_convex_strategy(non_convex_strategy) == False

