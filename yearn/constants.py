import os

from brownie import chain, convert
from y.networks import Network

CONCURRENCY = int(os.environ.get("CONCURRENCY", 1))

YFI = {
    Network.Mainnet: "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e",
    Network.Fantom: "0x29b0Da86e484E1C0029B56e817912d778aC0EC69",
    Network.Arbitrum: "0x82e3A8F066a6989666b031d916c43672085b1582",
    Network.Polygon: "0xDA537104D6A5edd53c6fBba9A898708E465260b6",
}.get(chain.id, None)

WRAPPED_GAS_COIN = {
    Network.Mainnet:            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    Network.Fantom:             "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83",
    Network.Arbitrum:           "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    Network.Gnosis:             "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d",
    Network.Optimism:           "0x4200000000000000000000000000000000000006",
    Network.Polygon:            "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
}.get(chain.id, None)

YEARN_ADDRESSES_PROVIDER = "0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93"
CURVE_ADDRESSES_PROVIDER = "0x0000000022D53366457F9d5E68Ec105046FC4383"

# EVENTS
ERC20_TRANSFER_EVENT_HASH  = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ERC677_TRANSFER_EVENT_HASH = '0xe19260aff97b920c7df27010903aeb9c8d2be5d310a2c67824cf3f15396e4c16'

# ADDRESSES
STRATEGIST_MULTISIG = {
    Network.Mainnet: {
        "0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7",
    },
    Network.Fantom: {
        "0x72a34AbafAB09b15E7191822A679f28E067C4a16",
    },
    Network.Gnosis: {
        "0xFB4464a18d18f3FF439680BBbCE659dB2806A187",
    },
    Network.Arbitrum: {
        "0x6346282db8323a54e840c6c772b4399c9c655c0d",
    },
    Network.Optimism: {
        "0xea3a15df68fCdBE44Fdb0DB675B2b3A14a148b26",
    },
    Network.Base: {
        "0x01fE3347316b2223961B20689C65eaeA71348e93",
    },
}.get(chain.id,set())

STRATEGIST_MULTISIG = {convert.to_address(address) for address in STRATEGIST_MULTISIG}

YCHAD_MULTISIG = {
    Network.Mainnet:    "0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52",
    Network.Fantom:     "0xC0E2830724C946a6748dDFE09753613cd38f6767",
    Network.Gnosis:     "0x22eAe41c7Da367b9a15e942EB6227DF849Bb498C",
    Network.Arbitrum:   "0xb6bc033d34733329971b938fef32fad7e98e56ad",
    Network.Optimism:   "0xF5d9D6133b698cE29567a90Ab35CfB874204B3A7",
    Network.Base:       "0xbfAABa9F56A39B814281D68d2Ad949e88D06b02E",
}.get(chain.id, None)

if YCHAD_MULTISIG:
    YCHAD_MULTISIG = convert.to_address(YCHAD_MULTISIG)

TREASURY_MULTISIG = {
    Network.Mainnet:    "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde",
    Network.Fantom:     "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a",
    Network.Arbitrum:   "0x1deb47dcc9a35ad454bf7f0fcdb03c09792c08c1",
    Network.Optimism:   "0x84654e35E504452769757AAe5a8C7C6599cBf954",
    Network.Base:       "0x02ff746D8cb62709aEEc611CeC9B17d7dD1D3480",
}.get(chain.id, None)

if TREASURY_MULTISIG:
    TREASURY_MULTISIG = convert.to_address(TREASURY_MULTISIG)

TREASURY_WALLETS = {
    Network.Mainnet: {
        TREASURY_MULTISIG,
        YCHAD_MULTISIG,
        "0xb99a40fcE04cb740EB79fC04976CA15aF69AaaaE", # Yearn Treasury V1  
        "0x5f0845101857d2A91627478e302357860b1598a1", # Yearn KP3R Wallet
        "0x7d2aB9CA511EBD6F03971Fb417d3492aA82513f0", # ySwap Multisig
        "0x2C01B4AD51a67E2d8F02208F54dF9aC4c0B778B6", # yMechs Multisig
    },
    Network.Fantom: {
        TREASURY_MULTISIG,
        YCHAD_MULTISIG,
    },
    Network.Gnosis: {
        YCHAD_MULTISIG,
        # TODO replace this with treasury msig
        #"0x5FcdC32DfC361a32e9d5AB9A384b890C62D0b8AC", # Yearn Treasury (EOA?)
    },
    Network.Arbitrum: {
        YCHAD_MULTISIG,
        TREASURY_MULTISIG,
    },
    Network.Optimism: {
        YCHAD_MULTISIG,
        TREASURY_MULTISIG,
    },
    Network.Base: {
        YCHAD_MULTISIG,
        TREASURY_MULTISIG, 
    }
}.get(chain.id,set())

TREASURY_WALLETS = {convert.to_address(address) for address in TREASURY_WALLETS}

RANDOMIZE_EXPORTS = bool(os.environ.get("RANDOMIZE_EXPORTS"))