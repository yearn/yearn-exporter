
import json

from brownie import Contract, chain, interface
from y import Contract_erc20
from y.constants import STABLECOINS
from y.networks import Network


def force_init_problematic_contracts() -> None:
    if chain.id == Network.Mainnet:
        # compile LINK contract locally for mainnet with latest solc because the etherscan abi crashes event parsing
        Contract.from_explorer("0x514910771AF9Ca656af840dff83E8264EcF986CA")

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
        
    elif chain.id == Network.Arbitrum:
        # PHP Philippine Peso stablecoin is not verified. Force starndard ERC-20 abi.
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
            "0xdf0770dF86a8034b3EFEf0A1Bb3c889B8332FF56": "S*USDC"
        },
    }.get(chain.id, {})

    for k, v in additional_stablecoins.items():
        STABLECOINS[k] = v
