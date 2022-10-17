from brownie import network, chain, Contract
from y import Contract_erc20
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
        # PHP Philippine Peso stablecoin is not verified. Force init it with ERC20 abi.
        Contract_erc20("0xFa247d0D55a324ca19985577a2cDcFC383D87953")
