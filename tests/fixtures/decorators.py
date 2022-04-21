
import pytest
from brownie import chain
from yearn.networks import Network

mainnet_only = pytest.mark.skipif(chain.id != Network.Mainnet, reason="Only applicable on Mainnet.")