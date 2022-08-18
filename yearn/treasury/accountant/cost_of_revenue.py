

from brownie import chain
from yearn.networks import Network
from yearn.treasury.accountant.classes import Filter, HashMatcher, TopLevelTxGroup

"""
- Gas
- Partner share
"""


COR_LABEL = "Cost of Revenue"

cost_of_revenue = TopLevelTxGroup(COR_LABEL)

hashes = {
    Network.Mainnet: {
        # Gas
        'strategists': [

        ],
        'thegraph': [
            '0x33a50699c95fa37e2cc4032719ed6064bbd892b0992dde01d4ef9b3470b9da0b',
        ],
        'yswap': [
            ['0xc66a60d1578ad80f9f1bfb29293bd9f8699c3d61b237a7cf8c443d00ffb3809e', Filter('from_address.label',"Disperse.app")],
            ['0xd45f5cf3388cea2a684ae124bac7bccb010442862cc491fdb4fc06d57c6aab5d', Filter('log_index',None)],
        ],
        'ychad': [
            ['0x1ba68f5f52b27e9b6676b952c08d29e2fe29f8ddffd7427911046915db5b4966', Filter('from_address.label',"Disperse.app")],
        ],
        'ymechs': [
            '0x1ab9ff3228cf25bf2a7c1eac596e836069f8c0adc46acd46d948eb77743fbb96',
            '0xe2a6bec23d0c73b35e969bc949072f8c1768767b06d57e5602b2b95eddf41a66',
        ],
        'ykeeper': [
            '0x1ab9ff3228cf25bf2a7c1eac596e836069f8c0adc46acd46d948eb77743fbb96',
            '0xe2a6bec23d0c73b35e969bc949072f8c1768767b06d57e5602b2b95eddf41a66',
        ],
        # Partners
        'partners': [
            '0xde77446e33ddce7ab9882932fb3d77dfb6913525ff67bc1ef1259d85aef421dc',
            '0xe04c2523837600102dade25eafefd6833c656d58da82bc6056273b98a013d2c1',
            '0xd20bb8befd0749e20d1dc40a8eb433d6ad5a0dfd3216a0318b2586bea90c2780',
            '0x01146721543ea5b95adf9c416c40ec92b8e4d37c36179cf98c1e651cb56b0399',
            '0x9b0824711f62068b403a84b0c577cf92a1b61599c5e6bca0665d1587ca9186fe',
            '0x311cbeb0b1b350832ef85ce5d2dfc1716b49023437f9ec0a402695f2103490bc',
            '0x092e366b3fb46aeaa2b2be95476fe69f95a293aee74590113a906975d63ad19b',
            '0x2d460d9205464f44e7510bcfab9ced5b5975066a10a9220da5e0fa74512fde5e',
            '0xa7cf40d300163de393323d8d209fabdb3f958e7d04474c56560e24356daf6e86',
        ]
    },
    Network.Fantom: {
        'partners': [

        ]
    }
}.get(chain.id, {})

gas = cost_of_revenue.create_child("Gas")
gas.create_child("Strategists", HashMatcher(hashes.get('strategists',[])).contains)
gas.create_child("TheGraph", HashMatcher(hashes.get('thegraph',[])).contains)
gas.create_child("ySwap Signers", HashMatcher(hashes.get('thegraph',[])).contains)
gas.create_child("yChad", HashMatcher(hashes.get('thegraph',[])).contains)
gas.create_child("yMechs", HashMatcher(hashes.get('thegraph',[])).contains)
gas.create_child("yKeeper", HashMatcher(hashes.get('thegraph',[])).contains)

cost_of_revenue.create_child("Yearn Partners", HashMatcher(hashes.get('partners',[])).contains)
