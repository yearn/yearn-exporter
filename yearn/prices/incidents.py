from collections import defaultdict

from brownie import chain

from yearn.networks import Network

INCIDENTS = defaultdict(list)

INCIDENTS.update({
    Network.Mainnet: {
        # yUSDC getPricePerFullShare reverts from block 10532764 to block 10532775 because all liquidity was removed for testing
        "0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e": [{"start":10532764,"end":10532775,"result":1}],
        "0x629c759D1E83eFbF63d84eb3868B564d9521C129": [{"start":11221202,"end":11238201,"result":1.037773031500707}],
        "0xcC7E70A958917cCe67B4B87a8C30E6297451aE98": [{"start":11512085,"end":11519723,"result":1.0086984562068226}],
        # GUSD vault state was broken due to an incident
        # https://github.com/yearn/yearn-security/blob/master/disclosures/2021-01-17.md
        "0xec0d8D3ED5477106c6D4ea27D90a60e594693C90": [{"start":11603873,"end":11645877,"result":0}],
        "0x5533ed0a3b83F70c3c4a1f69Ef5546D3D4713E44": [{"start":11865718,"end":11884721,"result":1.0345005219440915}],
        # yvcrvAAVE vault state was broken due to an incident
        # https://github.com/yearn/yearn-security/blob/master/disclosures/2021-05-13.md
        "0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab": [{"start":12430455,"end":12430661,"result":1.091553}],
        # yvust3CRV v1
        "0xF6C9E9AF314982A4b38366f4AbfAa00595C5A6fC": [
            {"start":11833643,"end":11833971,"result":1.0094921430595167},
            {"start":11893317,"end":12020551,"result":1.0107300938482453},
            {"start":12028696,"end":12194529,"result":1.0125968580471483},
        ],

        # for these, price cannot be fetched from chain because totalSupply == 0
        # on block of last withdrawal we return price at block - 1
        # after that block, returns 0

        # yvhusd3CRV v1
        "0x39546945695DCb1c037C836925B355262f551f55": [
            {"start":12074825,"end":12074825,"result":1.0110339337578227},
            {"start":12074826,"end":chain.height,"result":0},
        ],
        # yvobtccrv v1
        "0x7F83935EcFe4729c4Ea592Ab2bC1A32588409797": [
            {"start":12582511,"end":12582511,"result":37611.70819906929},
            {"start":12582512,"end":chain.height,"result":0},
        ],
        # yvpbtccrv v1
        "0x123964EbE096A920dae00Fb795FFBfA0c9Ff4675": [
            {"start":12868929,"end":12868929,"result":1456401056701488300032},
            {"start":12868930,"end":chain.height,"result":0},
        ],
    },
}.get(chain.id, {}))
