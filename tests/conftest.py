import os

from brownie import network

network.connect(os.environ.get('PYTEST_NETWORK','mainnet'))
