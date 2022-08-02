
from brownie import chain

from yearn.networks import Network


VAULT_ALIASES = {
    Network.Mainnet: {
        "0x29E240CFD7946BA20895a7a02eDb25C210f9f324": "aLINK",
        "0x881b06da56BB5675c54E4Ed311c21E54C5025298": "LINK",
        "0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e": "USDC",
        "0x5dbcF33D8c2E976c6b560249878e6F1491Bca25c": "curve.fi/y",
        "0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a": "TUSD",
        "0xACd43E627e64355f1861cEC6d3a6688B31a6F952": "DAI",
        "0x2f08119C6f07c006695E079AAFc638b8789FAf18": "USDT",
        "0xBA2E7Fed597fd0E3e70f5130BcDbbFE06bB94fe1": "YFI",
        "0x2994529C0652D127b7842094103715ec5299bBed": "curve.fi/busd",
        "0x7Ff566E1d69DEfF32a7b244aE7276b9f90e9D0f6": "curve.fi/sbtc",
        "0xe1237aA7f535b0CC33Fd973D66cBf830354D16c7": "WETH",
        "0x9cA85572E6A3EbF24dEDd195623F188735A5179f": "curve.fi/3pool",
        "0xec0d8D3ED5477106c6D4ea27D90a60e594693C90": "GUSD",
        "0x629c759D1E83eFbF63d84eb3868B564d9521C129": "curve.fi/compound",
        "0xcC7E70A958917cCe67B4B87a8C30E6297451aE98": "curve.fi/gusd",
        "0x0FCDAeDFb8A7DfDa2e9838564c5A1665d856AFDF": "curve.fi/musd",
        "0x98B058b2CBacF5E99bC7012DF757ea7CFEbd35BC": "curve.fi/eurs",
        "0xE0db48B4F71752C4bEf16De1DBD042B82976b8C7": "mUSD",
        "0x5334e150B938dd2b6bd040D9c4a03Cff0cED3765": "curve.fi/renbtc",
        "0xFe39Ce91437C76178665D64d7a2694B0f6f17fE3": "curve.fi/usdn",
        "0xF6C9E9AF314982A4b38366f4AbfAa00595C5A6fC": "curve.fi/ust",
        "0x7F83935EcFe4729c4Ea592Ab2bC1A32588409797": "curve.fi/obtc",
        "0x123964EbE096A920dae00Fb795FFBfA0c9Ff4675": "curve.fi/pbtc",
        "0x07FB4756f67bD46B748b16119E802F1f880fb2CC": "curve.fi/tbtc",
        "0xA8B1Cb4ed612ee179BDeA16CCa6Ba596321AE52D": "curve.fi/bbtc",
        "0x46AFc2dfBd1ea0c0760CAD8262A5838e803A37e5": "curve.fi/hbtc",
        "0x39546945695DCb1c037C836925B355262f551f55": "curve.fi/husd",
        "0x8e6741b456a074F0Bc45B8b82A755d4aF7E965dF": "curve.fi/dusd",
        "0x5533ed0a3b83F70c3c4a1f69Ef5546D3D4713E44": "curve.fi/susd",
        "0x03403154afc09Ce8e44C3B185C82C6aD5f86b9ab": "curve.fi/aave",
        "0xE625F5923303f1CE7A43ACFEFd11fd12f30DbcA4": "curve.fi/ankreth",
        "0xBacB69571323575C6a5A3b4F9EEde1DC7D31FBc1": "curve.fi/saave",
        "0x1B5eb1173D2Bf770e50F10410C9a96F7a8eB6e75": "curve.fi/usdp",
        "0x96Ea6AF74Af09522fCB4c28C269C26F59a31ced6": "curve.fi/link",
    },
}.get(chain.id, {})