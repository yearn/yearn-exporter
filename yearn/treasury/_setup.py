from brownie import chain
from eth_portfolio._shitcoins import SHITCOINS
from y.networks import Network
from y.prices.utils import ypriceapi

# The below tokens mess up our scripts, mean nothing for analytical purposes, and can be skipped by eth_portfolio
skip_tokens = {
    Network.Mainnet: {
        "0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85", # ENS domain
        "0xD1E5b0FF1287aA9f9A268759062E4Ab08b9Dacbe", # Unstoppable Domains
        "0xeF81c2C98cb9718003A89908e6bd1a5fA8A098A3", # SpaceShibas NFT
        "0xD7aBCFd05a9ba3ACbc164624402fB2E95eC41be6", # Eth Juanchos
        "0x01234567bac6fF94d7E4f0EE23119CF848F93245", # ETH Blocks
        "0x437a6B880d4b3Be9ed93BD66D6B7f872fc0f5b5E", # Soda
        "0x9d45DAb69f1309F1F55A7280b1f6a2699ec918E8", # yFamily 2021
        "0xeaaa790591c646b0436f02f63e8Ca56209FEDE4E", # D-Horse
        "0x1e988ba4692e52Bc50b375bcC8585b95c48AaD77", # Bufficorn Buidl Brigade
    }
}

def customize_eth_portfolio() -> None:
    for token in skip_tokens.get(chain.id, []):
        SHITCOINS[chain.id].add(token)


skip_ypriceapi = {
    Network.Mainnet: {
        "0xD057B63f5E69CF1B929b356b579Cba08D7688048", # vCOW
        "0x9aE357521153FB07bE6F5792CE7a49752638fbb7", # SAFE
        "0x739ca6D71365a08f584c8FC4e1029045Fa8ABC4B", # anyDAI
        "0x3f6740b5898c5D3650ec6eAce9a649Ac791e44D7", # kLP-KP3R/WETH
    },
}
        
def customize_ypricemagic() -> None:
    """We just do this to reduce unnecessary and ugly logging.""" 
    for token in skip_ypriceapi.get(chain.id, []):
        ypriceapi.skip_ypriceapi.add(token)
