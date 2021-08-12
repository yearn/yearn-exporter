from brownie import interface

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
    "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D",
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "0xfE18be6b3Bd88A2D2A7f928d00292E7a9963CfC6",
}

ETH_LIKE = {
    "0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb",
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
}

YEARN_ADDRESSES_PROVIDER = "0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93"
CURVE_ADDRESSES_PROVIDER = "0x0000000022D53366457F9d5E68Ec105046FC4383"

CURVE_SWAP_POOLS = [
    {
        "has_single_sided_deposit": "true",
        "address": "0x7fC77b5c7614E1533320Ea6DDc2Eb61fa00A9714",
        "name": "sBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
        "name": "3Pool",
    },
    {
        "has_single_sided_deposit": "true",
        "has_no_pool_info": "true",
        "address": "0xd632f22692FaC7611d2AA1C0D552930D43CAEd3B",
        "name": "Frax",
    },
    {
        "has_single_sided_deposit": "true",
        "has_no_pool_info": "true",
        "address": "0x4807862AA8b2bF68830e4C8dc86D0e9A998e085a",
        "name": "Binance USD",
    },
    {
        "has_single_sided_deposit": "true",
        "has_no_pool_info": "true",
        "address": "0x43b4FdFD4Ff969587185cDB6f0BD875c5Fc83f8c",
        "name": "Alchemix USD",
    },
    {
        "has_single_sided_deposit": "true",
        "has_no_pool_info": "true",
        "address": "0xFD5dB7463a3aB53fD211b4af195c5BCCC1A03890",
        "name": "Euro Tether",
    },
    {
        "has_single_sided_deposit": "true",
        "has_no_pool_info": "true",
        "address": "0x5a6A4D54456819380173272A5E8E9B9904BdF41B",
        "name": "MIM",
    },
    {
        "has_single_sided_deposit": "false",
        "has_no_pool_info": "true",
        "address": "0xD51a44d3FaE010294C616388b506AcdA1bfAAE46",
        "name": "TriCrypto 2",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xEcd5e75AFb02eFa118AF914515D6521aaBd189F1",
        "name": "TrueUSD",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x8925D9d9B4569D737a48499DeF3f67BaA5a144b9",
        "name": "Yv2",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xA96A65c051bF88B4095Ee1f2451C2A9d43F53Ae2",
        "name": "ankrETH",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xDeBF20617708857ebe4F679508E7b7863a8A8EeE",
        "name": "AAVE",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x79a8C46DeA5aDa233ABaFFD40F3A0A2B1e5A4F27",
        "name": "BUSD",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xA2B47E3D5c44877cca798226B7B8118F9BFb7A56",
        "name": "Compound",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x0Ce6a5fF5217e38315f87032CF90686C96627CAA",
        "name": "EURS",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x4CA9b3063Ec5866A4B82E437059D2C43d1be596F",
        "name": "hBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x2dded6Da1BF5DBdF597C45fcFaa3194e53EcfeAF",
        "name": "IronBank",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xf178c0b5bb7e7abf4e12a4838c7b7c5ba2c623c0",
        "name": "Link",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x06364f10B501e868329afBc005b3492902d6C763",
        "name": "PAX",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x93054188d876f558f4a66B2EF1d97d16eDf0895B",
        "name": "renBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xF9440930043eb3997fc70e1339dBb11F341de7A8",
        "name": "rETH",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xEB16Ae0052ed37f479f7fe63849198Df1765a733",
        "name": "sAAVE",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xc5424B857f758E906013F3555Dad202e4bdB4567",
        "name": "sETH",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xDC24316b9AE028F1497c275EB9192a3Ea0f67022",
        "name": "stETH",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xA5407eAE9Ba41422680e2e00537571bcC53efBfD",
        "name": "sUSD",
    },
    {
        "has_single_sided_deposit": "false",
        "address": "0x52EA46506B9CC5Ef470C5bf89f17Dc28bB35D85C",
        "name": "USDT",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x45F783CCE6B7FF23B2ab2D70e416cdb7D6055f51",
        "name": "Y",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x7F55DDe206dbAD629C080068923b36fe9D6bDBeF",
        "name": "pBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x0Ce6a5fF5217e38315f87032CF90686C96627CAA",
        "name": "EURS",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x8038C01A0390a8c547446a0b2c18fc9aEFEcc10c",
        "name": "DUSD",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x4f062658EaAF2C1ccf8C8e36D6824CDf41167956",
        "name": "GUSD",
    },
    {
        "has_single_sided_deposit": "false",
        "address": "0x3eF6A01A0f81D6046290f3e2A8c5b843e738E604",
        "name": "HUSD",
    },
    {
        "has_single_sided_deposit": "false",
        "address": "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD7D171",
        "name": "LinkUSD",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x8474DdbE98F5aA3179B3B3F5942D724aFcdec9f6",
        "name": "MUSD",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xC18cC39da8b11dA8c3541C598eE022258F9744da",
        "name": "RSV",
    },
    {
        "has_single_sided_deposit": "false",
        "address": "0x3E01dD8a5E1fb3481F0F589056b428Fc308AF0Fb",
        "name": "USDK",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x0f9cb53Ebe405d49A0bbdBD291A65Ff571bC83e1",
        "name": "USDN",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x42d7025938bEc20B69cBae5A77421082407f053A",
        "name": "USDP",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x890f4e345B1dAED0367A877a1612f86A1f86985f",
        "name": "UST",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x071c661B4DeefB59E2a3DdB20Db036821eeE8F4b",
        "name": "bBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xd81dA8D904b52208541Bade1bD6595D8a251F8dd",
        "name": "oBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0x7F55DDe206dbAD629C080068923b36fe9D6bDBeF",
        "name": "pBTC",
    },
    {
        "has_single_sided_deposit": "true",
        "address": "0xC25099792E9349C7DD09759744ea681C7de2cb66",
        "name": "tBTC",
    },
    {
        "has_single_sided_deposit": "false",
        "address": "0xEd279fDD11cA84bEef15AF5D39BB4d4bEE23F0cA",
        "name": "Liquity",
    },
]

POOL_INFO_CONTRACT = '0xe64608E223433E8a03a1DaaeFD8Cb638C14B552C'

SINGLE_SIDED_UNDERLYING_TOKENS = {
    "0x6B175474E89094C44Da98b954EedeAC495271d0F": "DAI",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",
    "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51": "SUSD",
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": "WBTC",
    "0xfE18be6b3Bd88A2D2A7f928d00292E7a9963CfC6": "sBTC",
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "ETH",
    "0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb": "sETH",
    "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84": "stETH",
    "0x5228a22e72ccC52d415EcFd199F99D0665E7733b": "pBTC",
    "0x075b1bb99792c9E1041bA13afEf80C91a1e70fB3": "sBTC",
}

SINGLE_SIDED_TOKENS = {
    "0x6B175474E89094C44Da98b954EedeAC495271d0F": "DAI",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",
    "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51": "SUSD",
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": "WBTC",
    "0xfE18be6b3Bd88A2D2A7f928d00292E7a9963CfC6": "sBTC",
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "ETH",
    "0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb": "sETH",
    "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84": "stETH",
    "0x8e595470Ed749b85C6F7669de83EAe304C2ec68F": "cyDAI",
    "0x76Eb2FE28b36B3ee97F3Adae0C69606eeDB2A37c": "cyUSDC",
    "0x48759F220ED983dB51fA7A8C0D2AAb8f3ce4166a": "cyUSDT",
    "0x028171bCA77440897B824Ca71D1c56caC55b68A3": "aDAI",
    "0x6C5024Cd4F8A59110119C56f8933403A539555EB": "aSUSD",
    "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D": "renBTC",
    "0x5228a22e72ccC52d415EcFd199F99D0665E7733b": "pBTC",
    "0x075b1bb99792c9E1041bA13afEf80C91a1e70fB3": "sBTC",
}
