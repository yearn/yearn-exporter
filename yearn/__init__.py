import json

from brownie import Contract, chain, network

from yearn.logs import setup_logging
from yearn.networks import Network
from yearn.sentry import setup_sentry

setup_logging()
setup_sentry()

if network.is_connected():
    from y import Contract_erc20

    from yearn.middleware.middleware import setup_middleware
    setup_middleware()

    if chain.id == Network.Mainnet:
        # LINK abi from etherscan crashes event parsing, use a compiled one
        Contract.from_abi(
            name="ChainLink Token",
            address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
            abi=json.load(open("interfaces/chainlink/LinkToken.json"))
        )
        # XEN abi from etherscan is missing events
        Contract.from_abi(
            name="XENCrypto",
            address="0x06450dEe7FD2Fb8E39061434BAbCFC05599a6Fb8",
            abi=json.load(open("interfaces/XEN.json"))
        )
        # cEUR stablecoin has busted abi
        Contract.from_abi(
            name="TokenBridge",
            address="0xEE586e7Eaad39207F0549BC65f19e336942C992f",
            abi=json.load(open("interfaces/ERC20.json"))
        )
        # UST (Wormhole)
        Contract.from_abi(
            name="TokenBridge",
            address="0xa693B19d2931d498c5B318dF961919BB4aee87a5",
            abi=json.load(open("interfaces/ERC20.json"))
        )

        # TricryptoUSDT (crvUSDTWBTCWETH) partially verified on etherscan
        Contract.from_abi(
            name="CurveTricryptoOptimizedWETH",
            address="0xf5f5B97624542D72A9E06f04804Bf81baA15e2B4",
            abi=json.load(open("interfaces/curve/tricrypto-ng/CurveTricryptoOptimizedWETH.json"))
        )

        # LiquidityGauge (crvUSDCWBTCWETH-gauge) not verified on etherscan
        Contract.from_abi(
            name="Curve.fi crvUSDCWBTCWETH Gauge Deposit ",
            address="0x85D44861D024CB7603Ba906F2Dc9569fC02083F6",
            abi=json.load(open("interfaces/curve/tricrypto-ng/LiquidityGauge.json"))
        )
    elif chain.id == Network.Arbitrum:
        # PHP Philippine Peso stablecoin is not verified. Force init it with ERC20 abi.
        Contract_erc20("0xFa247d0D55a324ca19985577a2cDcFC383D87953")
        
        # workaround for issues loading the partner tracker contract on arbitrum
        Contract.from_abi(
            name='YearnPartnerTracker',
            address='0x0e5b46E4b2a05fd53F5a4cD974eb98a9a613bcb7',
            abi=json.load(open('interfaces/yearn/partner_tracker_arbitrum.json'))
        )
