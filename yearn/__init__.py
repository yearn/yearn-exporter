import json
from brownie import network, chain, Contract
from yearn.networks import Network
from yearn.logs import setup_logging
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()

if network.is_connected():
    from yearn.middleware.middleware import setup_middleware
    setup_middleware()

    if chain.id == Network.Mainnet:
        # compile LINK contract locally for mainnet with latest solc because the etherscan abi crashes event parsing
        Contract.from_explorer("0x514910771AF9Ca656af840dff83E8264EcF986CA")

    elif chain.id == Network.Arbitrum:
        # workaround for issues loading the partner tracker contract on arbitrum
        Contract.from_abi(
            name='YearnPartnerTracker',
            address='0x0e5b46E4b2a05fd53F5a4cD974eb98a9a613bcb7',
            abi=json.load(open('interfaces/yearn/partner_tracker_arbitrum.json'))
        )
