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
        "0x9694EED198C1b7aB81ADdaf36255Ea58acf13Fab", # DHX
        "0x55a290f08Bb4CAe8DcF1Ea5635A3FCfd4Da60456", # BITTO
        "0x1AbBaC88B8F47D46a3d822eFA75F64A15C25966f", # YBET
        "0x32002658029DA06fFFCFbad58706AA325B3e236e", # ZRO
        "0xA612F9e9Ba5e3b57B0D64DE4bDFccD36e08f3E6a", # aUSD
        "0x5cB5e2d7Ab9Fd32021dF8F1D3E5269bD437Ec3Bf", # aUSD
        "0xE256CF1C7caEff4383DabafEe6Dd53910F97213D", # DWS
        "0x528Ff33Bf5bf96B5392c10bc4748d9E9Fb5386B2", # PRM
    },
    Network.Arbitrum: {
        "0x89b0f9dB18FD079063cFA91F174B300C1ce0003C", # AIELON
    },
}

def customize_eth_portfolio() -> None:
    for token in skip_tokens.get(chain.id, []):
        if chain.id not in SHITCOINS:
            SHITCOINS[chain.id] = set()
        SHITCOINS[chain.id].add(token)


skip_ypriceapi = {
    Network.Mainnet: {
        "0x739ca6D71365a08f584c8FC4e1029045Fa8ABC4B", # anyDAI
        "0x7EA2be2df7BA6E54B1A9C70676f668455E329d29", # anyUSDC
        "0xbbc4A8d076F4B1888fec42581B6fc58d242CF2D5", # anyMIM
        "0xdf0770dF86a8034b3EFEf0A1Bb3c889B8332FF56", # S*USDC
        "0xEdB67Ee1B171c4eC66E6c10EC43EDBbA20FaE8e9", # rKP3R
        "0x3f6740b5898c5D3650ec6eAce9a649Ac791e44D7", # kLP-KP3R/WETH
        "0xD057B63f5E69CF1B929b356b579Cba08D7688048", # vCOW
        "0x9aE357521153FB07bE6F5792CE7a49752638fbb7", # SAFE
        "0x7E46fd8a30869aa9ed55af031067Df666EfE87da", # yvecrv-f (deprecated)
        "0xC4C319E2D4d66CcA4464C0c2B32c9Bd23ebe784e", # aleth+eth-f (exploited)
    },
    Network.Fantom: {
        "0x6362496Bef53458b20548a35A2101214Ee2BE3e0", # anyFTM
        "0xd652776dE7Ad802be5EC7beBfafdA37600222B48", # anyDAI
    },
}
        
def customize_ypricemagic() -> None:
    """We just do this to reduce unnecessary and ugly logging.""" 
    for token in skip_ypriceapi.get(chain.id, []):
        ypriceapi.skip_ypriceapi.add(token)
