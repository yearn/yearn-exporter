from brownie import interface, chain
from yearn.networks import Network

WRAPPED_GAS_COIN = {
    Network.Mainnet:            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    Network.Fantom:             "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83",
    Network.Arbitrum:           "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    Network.Gnosis:             "0xe91d153e0b41518a2ce8dd3d7944fa863463a97d",
}.get(chain.id, None)

CONTROLLER_INTERFACES = {
    "0x2be5D998C95DE70D9A38b3d78e49751F10F9E88b": interface.ControllerV1,
    "0x9E65Ad11b299CA0Abefc2799dDB6314Ef2d91080": interface.ControllerV2,
}

VAULT_INTERFACES = {
    "0x29E240CFD7946BA20895a7a02eDb25C210f9f324": interface.yDelegatedVault,
    "0x881b06da56BB5675c54E4Ed311c21E54C5025298": interface.yWrappedVault,
    "0xc5bDdf9843308380375a611c18B50Fb9341f502A": interface.yveCurveVault,
}

STRATEGY_INTERFACES = {
    "0x25fAcA21dd2Ad7eDB3a027d543e617496820d8d6": interface.StrategyVaultUSDC,
    "0xA30d1D98C502378ad61Fe71BcDc3a808CF60b897": interface.StrategyDForceUSDC,
    "0x1d91E3F77271ed069618b4BA06d19821BC2ed8b0": interface.StrategyTUSDCurve,
    "0xAa880345A3147a1fC6889080401C791813ed08Dc": interface.StrategyDAICurve,
    "0x787C771035bDE631391ced5C083db424A4A64bD8": interface.StrategyDForceUSDT,
    "0x932fc4fd0eEe66F22f1E23fBA74D7058391c0b15": interface.StrategyMKRVaultDAIDelegate,
    "0xF147b8125d2ef93FB6965Db97D6746952a133934": interface.CurveYCRVVoter,
    "0x112570655b32A8c747845E0215ad139661e66E7F": interface.StrategyCurveBUSDVoterProxy,
    "0x6D6c1AD13A5000148Aa087E7CbFb53D402c81341": interface.StrategyCurveBTCVoterProxy,
    "0x07DB4B9b3951094B9E278D336aDf46a036295DE7": interface.StrategyCurveYVoterProxy,
    "0xC59601F0CC49baa266891b7fc63d2D5FE097A79D": interface.StrategyCurve3CrvVoterProxy,
    "0x395F93350D5102B6139Abfc84a7D6ee70488797C": interface.StrategyYFIGovernance,
    "0xc8327D8E1094a94466e05a2CC1f10fA70a1dF119": interface.StrategyCurveGUSDProxy,
    "0x530da5aeF3c8f9CCbc75C97C182D6ee2284B643F": interface.StrategyCurveCompoundVoterProxy,
    "0x4720515963A9d40ca10B1aDE806C1291E6c9A86d": interface.StrategyUSDC3pool,
    "0xe3a711987612BFD1DAFa076506f3793c78D81558": interface.StrategyTUSDypool,
    "0xc7e437033D849474074429Cbe8077c971Ea2a852": interface.StrategyUSDT3pool,
    "0xBA0c07BBE9C22a1ee33FE988Ea3763f21D0909a0": interface.StrategyCurvemUSDVoterProxy,
    "0xD42eC70A590C6bc11e9995314fdbA45B4f74FABb": interface.StrategyCurveGUSDVoterProxy,
    "0xF4Fd9B4dAb557DD4C9cf386634d61231D54d03d6": interface.StrategyGUSDRescue,
    "0x9c211BFa6DC329C5E757A223Fb72F5481D676DC1": interface.StrategyDAI3pool,
    "0x39AFF7827B9D0de80D86De295FE62F7818320b76": interface.StrategyMKRVaultDAIDelegate,
    "0x22422825e2dFf23f645b04A3f89190B69f174659": interface.StrategyCurveEURVoterProxy,
    "0x6f1EbF5BBc5e32fffB6B3d237C3564C15134B8cF": interface.StrategymUSDCurve,
    "0x76B29E824C183dBbE4b27fe5D8EdF0f926340750": interface.StrategyCurveRENVoterProxy,
    "0x406813fF2143d178d1Ebccd2357C20A424208912": interface.StrategyCurveUSDNVoterProxy,
    "0x3be2717DA725f43b7d6C598D8f76AeC43e231B99": interface.StrategyCurveUSTVoterProxy,
    "0x15CfA851403aBFbbD6fDB1f6fe0d32F22ddc846a": interface.StrategyCurveOBTCVoterProxy,
    "0xD96041c5EC05735D965966bF51faEC40F3888f6e": interface.StrategyCurvePBTCVoterProxy,
    "0x61A01a704665b3C0E6898C1B4dA54447f561889d": interface.StrategyCurveTBTCVoterProxy,
    "0x551F41aD4ebeCa4F5d025D2B3082b7AB2383B768": interface.StrategyCurveBBTCVoterProxy,
    "0xE02363cB1e4E1B77a74fAf38F3Dbb7d0B70F26D7": interface.StrategyCurveHBTCVoterProxy,
    "0xd7F641697ca4e0e19F6C9cF84989ABc293D24f84": interface.StrategyCurvesUSDVoterProxy,
    "0xb21C4d2f7b2F29109FF6243309647A01bEB9950a": interface.StrategyCurveHUSDVoterProxy,
    "0x33F3f002b8f812f3E087E9245921C8355E777231": interface.StrategyCurveDUSDVoterProxy,
    "0x7A10bE29c4d9073E6B3B6b7D1fB5bCDBecA2AA1F": interface.StrategyCurvea3CRVVoterProxy,
    "0xBdCeae91e10A80dbD7ad5e884c86EAe56b075Caa": interface.StrategyCurveAnkrVoterProxy,
    "0x2F90c531857a2086669520e772E9d433BbfD5496": interface.StrategyDAI3pool,
    "0xBcC6abd115a32fC27f7B49F9e17D0BcefDd278aC": interface.StrategyCurvemUSDVoterProxy,
    "0x83e7399113561ae691c413ed334137D3839e2302": interface.StrategyCurveEURVoterProxy,
    "0x4f2fdebE0dF5C92EEe77Ff902512d725F6dfE65c": interface.StrategyUSDC3pool,
    "0xAa12d6c9d680EAfA48D8c1ECba3FCF1753940A12": interface.StrategyUSDT3pool,
    "0x4BA03330338172fEbEb0050Be6940c6e7f9c91b0": interface.StrategyTUSDypool,
    "0x8e2057b8fe8e680B48858cDD525EBc9510620621": interface.StrategyCurvesaCRVVoterProxy,
}

VAULT_ALIASES = {
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
}

BTC_LIKE = {
    "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D", # renbtc
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", # wbtc
    "0xfE18be6b3Bd88A2D2A7f928d00292E7a9963CfC6", # sbtc
    "0x8064d9Ae6cDf087b1bcd5BDf3531bD5d8C537a68", # obtc
    "0x9BE89D2a4cd102D8Fecc6BF9dA793be995C22541", # bbtc
    "0x0316EB71485b0Ab14103307bf65a021042c6d380", # hbtc
    "0x5228a22e72ccC52d415EcFd199F99D0665E7733b", # pbtc
    "0x8dAEBADE922dF735c38C80C7eBD708Af50815fAa", # tbtc
}

ETH_LIKE = {
    "0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb", # seth
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", # eth
    "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", # steth
    "0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593", # reth
    "0xE95A203B1a91a908F9B9CE46459d101078c2c3cb", # ankreth
}

YEARN_ADDRESSES_PROVIDER = "0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93"
CURVE_ADDRESSES_PROVIDER = "0x0000000022D53366457F9d5E68Ec105046FC4383"


# EVENTS
ERC20_TRANSFER_EVENT_HASH  = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ERC677_TRANSFER_EVENT_HASH = '0xe19260aff97b920c7df27010903aeb9c8d2be5d310a2c67824cf3f15396e4c16'

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
    }
}.get(chain.id,set())

YCHAD_MULTISIG = {
    Network.Mainnet:    "0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52",
    Network.Fantom:     "0xC0E2830724C946a6748dDFE09753613cd38f6767",
    Network.Gnosis:     "0x22eAe41c7Da367b9a15e942EB6227DF849Bb498C",
    Network.Arbitrum:   "0xb6bc033d34733329971b938fef32fad7e98e56ad",
}.get(chain.id, None)

TREASURY_MULTISIG = {
    Network.Mainnet:    "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde",
    Network.Fantom:     "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a",
    Network.Arbitrum:   "0x1deb47dcc9a35ad454bf7f0fcdb03c09792c08c1",
}.get(chain.id, None)

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
        "0x5FcdC32DfC361a32e9d5AB9A384b890C62D0b8AC", # Yearn Treasury (EOA?)
    },
}.get(chain.id,set())
