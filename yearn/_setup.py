
import json
import logging
import os

from brownie import chain
from y import Contract, Contract_erc20
from y.constants import STABLECOINS
from y.networks import Network


def force_init_problematic_contracts() -> None:
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
        Contract_erc20("0xEE586e7Eaad39207F0549BC65f19e336942C992f")

        # UST (Wormhole)
        Contract_erc20("0xa693B19d2931d498c5B318dF961919BB4aee87a5")

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

        # CREAM unitroller
        Contract.from_explorer("0xbadaC56c9aca307079e8B8FC699987AAc89813ee")

        # workaround for issues loading the partner tracker contract on arbitrum
        Contract.from_abi(
            name='YearnPartnerTracker',
            address='0x0e5b46E4b2a05fd53F5a4cD974eb98a9a613bcb7',
            abi=json.load(open('interfaces/yearn/partner_tracker_arbitrum.json'))
        )

def customize_ypricemagic() -> None:
    additional_stablecoins = {
        Network.Mainnet: {
            "0x739ca6D71365a08f584c8FC4e1029045Fa8ABC4B": "anyDAI",
            "0x7EA2be2df7BA6E54B1A9C70676f668455E329d29": "anyUSDC",
            "0xbbc4A8d076F4B1888fec42581B6fc58d242CF2D5": "anyMIM",
            "0xdf0770dF86a8034b3EFEf0A1Bb3c889B8332FF56": "S*USDC",
        },
        Network.Fantom: {
            "0xd652776dE7Ad802be5EC7beBfafdA37600222B48": "anyDAI",
        },
    }.get(chain.id, {})

    for k, v in additional_stablecoins.items():
        STABLECOINS[k] = v

def configure_loggers():
    if config_settings := os.environ.get("LOGGER_LEVELS"):
        for logger_config in config_settings.split(','):
            logger_name, level = logger_config.split(':')
            logging.getLogger(logger_name).setLevel(getattr(logging, level.upper()))