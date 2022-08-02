from brownie import chain, convert

from yearn.networks import Network

tokens_by_network = {
    Network.Mainnet: {
        'weth': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        'usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'dai': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
    },
    Network.Gnosis: {
        'weth': '0x6A023CCd1ff6F2045C3309768eAd9E68F978f6e1',
        'usdc': '0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83',
        'dai': '0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d', # wxdai address
    },
    Network.Fantom: {
        'weth': '0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83',
        'usdc': '0x04068DA6C83AFCFA0e13ba15A6696662335D5B75',
        'dai': '0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E',
    },
    Network.Arbitrum: {
        'weth': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
        'usdc': '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8',
        'dai': '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1',
    },
}

stablecoins_by_network = {
    Network.Mainnet: {
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "usdc",
        "0x0000000000085d4780B73119b644AE5ecd22b376": "tusd",
        "0x6B175474E89094C44Da98b954EedeAC495271d0F": "dai",
        "0xdAC17F958D2ee523a2206206994597C13D831ec7": "usdt",
        "0x4Fabb145d64652a948d72533023f6E7A623C7C53": "busd",
        "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51": "susd",
        "0x1456688345527bE1f37E9e627DA0837D6f08C925": "usdp",
        "0x674C6Ad92Fd080e4004b2312b45f796a192D27a0": "usdn",
        "0x853d955aCEf822Db058eb8505911ED77F175b99e": "frax",
        "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0": "lusd",
        "0xBC6DA0FE9aD5f3b0d58160288917AA56653660E9": "alusd",
        "0x0000000000085d4780B73119b644AE5ecd22b376": "tusd",
        "0x1c48f86ae57291F7686349F12601910BD8D470bb": "usdk",
        "0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd": "gusd",
        "0x0E2EC54fC0B509F445631Bf4b91AB8168230C752": "linkusd",
        "0x99D8a9C45b2ecA8864373A26D1459e3Dff1e17F3": "mim",
        "0xa47c8bf37f92aBed4A126BDA807A7b7498661acD": "ust",
        "0x196f4727526eA7FB1e17b2071B3d8eAA38486988": "rsv",
        "0xdF574c24545E5FfEcb9a659c229253D4111d87e1": "husd",
        "0x5BC25f649fc4e26069dDF4cF4010F9f706c23831": "dusd",
        "0xe2f2a5C287993345a840Db3B0845fbC70f5935a5": "musd",
        "0x739ca6D71365a08f584c8FC4e1029045Fa8ABC4B": "anydai",
        "0xbbc4A8d076F4B1888fec42581B6fc58d242CF2D5": "anymim",
        "0x865377367054516e17014CcdED1e7d814EDC9ce4": "dola",
    },
    Network.Gnosis: {
        "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83": "usdc",
        "0x4ECaBa5870353805a9F068101A40E0f32ed605C6": "usdt",
        "0xe91d153e0b41518a2ce8dd3d7944fa863463a97d": "wxdai"
    },
    Network.Fantom: {
        "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75": "usdc",
        "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E": "dai",
        "0x1B27A9dE6a775F98aaA5B90B62a4e2A0B84DbDd9": "usdt",
        "0xC931f61B1534EB21D8c11B24f3f5Ab2471d4aB50": "busd",
        "0xe2D27f06F63d98b8e11b38b5b08A75D0c8dD62B9": "ust",
        "0x82f0B8B456c1A451378467398982d4834b6829c1": "mim",
        "0x049d68029688eAbF473097a2fC38ef61633A3C7A": "fusdt",
        "0xdc301622e621166BD8E82f2cA0A26c13Ad0BE355": "frax",
        "0x95bf7E307BC1ab0BA38ae10fc27084bC36FcD605": "anyusdc",
        "0xd652776dE7Ad802be5EC7beBfafdA37600222B48": "anydai",
        "0x3129662808bEC728a27Ab6a6b9AFd3cBacA8A43c": "dola",
    },
    Network.Arbitrum: {
        '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8': 'usdc',
        '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1': 'dai',
        '0xFEa7a6a0B346362BF88A9e4A88416B77a57D6c2A': 'mim',
        '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9': 'usdt'
    },
}

ib_snapshot_block_by_network = {
    Network.Mainnet: 14051986,
    Network.Fantom: 28680044,
    Network.Gnosis: 1, # TODO revisit as IB is not deployed in gnosis
    Network.Arbitrum: 1
}

# We convert to checksum address here to prevent minor annoyances. It's worth it.
weth = convert.to_address(tokens_by_network[chain.id]['weth'])
usdc = convert.to_address(tokens_by_network[chain.id]['usdc'])
dai  = convert.to_address(tokens_by_network[chain.id]['dai'])
stablecoins = {convert.to_address(coin): symbol for coin, symbol in stablecoins_by_network[chain.id].items()}
ib_snapshot_block = ib_snapshot_block_by_network[chain.id]
