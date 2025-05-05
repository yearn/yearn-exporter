
import eth_portfolio
from brownie import chain
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
        "0x53fFFB19BAcD44b82e204d036D579E86097E5D09", # BGBG
        "0x57b9d10157f66D8C00a815B5E289a152DeDBE7ed", # 环球股
        "0x1d41cf24dF81E3134319BC11c308c5589A486166", # Strangers NFT from @marcoworms <3
        "0x1BA4b447d0dF64DA64024e5Ec47dA94458C1e97f", # Hegic V8888 Options (Tokenized)
        "0xC36442b4a4522E871399CD717aBDD847Ab11FE88", # Uni V3 NonfungiblePositionManager
        "0x3f6740b5898c5D3650ec6eAce9a649Ac791e44D7", # Uni V3 UniV3PairManager
        "0x3EF9181c9b96BAAafb3717A553E808Ccc72be37D", # MEMEPEPE
        "0x0329b631464C43f4e8132df7B4ac29a2D89FFdC7", # YFI2.0
        "0x594DaaD7D77592a2b97b725A7AD59D7E188b5bFa", # APU
        "0x05bAdF8A8e7fE5b43fae112108E26f2f663Bf1a2", # INUNOMICS
        "0x927402ab67c0CDA3c187E9DFE34554AC581441f2", # SAITABIT
        "0x875bf9be244970B8572DD042053508bF758371Ee", # fake SOLID

        # these arent shitcoins per se but we can't price them and dont expect to in the future, lets save cpu cycles
        "0xD057B63f5E69CF1B929b356b579Cba08D7688048", # vCOW
        "0x4c1317326fD8EFDeBdBE5e1cd052010D97723bd6", # deprecated yCRV
        "0x8a0889d47f9Aa0Fac1cC718ba34E26b867437880", # deprecated st-yCRV

        # test token?
        "0x372d5d02c6b4075bd58892f80300cA590e92d29E", # tOUSG

        # TODO: put these in eth-port
        "0x6cC759B8cE30e719511B6a897CfE449A19f64a92", # spamcoin

        "0x59bed83a385571ffac0FC15A43f0f6f72e66Dccb", # ERC20?
        "0x3B809ABd5a7597F8d1cf7dEB2747A1e1580C1488", # ERC20?

        "0x5bb38F4899797f03141782E9d2130C12769c0CCc",
        "0x570EC272F07c563860477DCAfB04a04FFd2979a1",

        # a bunch of silly AI related spam tokens

        "0x1495Ac869433698cCD2946c1e62D37bA766294A9",
        "0x1F7B20004eBd7E258b9f45568cE789fC5d2140fb",
        "0x37843BC944eDBb0477df943d9061D359004a4e70",
        "0x4D57c67C8Bab0Fb3A0a0A35B904FBff4E5450521",
        "0x4e6c80aa486aF0ba20943Fbc067a5557DBcf5458",
        "0x5bb38F4899797f03141782E9d2130C12769c0CCc",
        "0x5be480Aa056ec274e5aE970d7A75dF0c9620F6F8",
        "0x5D22c8b4E3c90ca633e1377e6ca280a395fc61C0",
        "0x64b3336D1aDC6D3579e356760F53D3b018Cb11Bc",
        "0x6Ac9cA5710Ba6B985b46fd5282a59eBbea3434d4",
        "0x7CE31075d7450Aff4A9a82DdDF69D451B1e0C4E9",
        "0x7d09A736c5FB1Db357dE04A07DEB22D5829DA26F",
        "0x83D473D1acD97Aa45A97c3b778fB5714e7e4c604",
        "0x884a886D17a64852d18e5921fA7A05ae2954C9Bb",
        "0x8c0DF275c38092cd90Ae4d6147d8e619B3A24637",
        "0x9A7ddeE20b61EA4f4812665EdF39dD157a66E873",
        "0xA1f76F1c94078f7d2E05152DC3e31dED819dfDC0",
        "0xa65D56f8e074E773142205cD065FD0796B9aa483",
        "0xaf80B7dbeBbb5d9a4d33C453FcbF3d054DA53b25",
        "0xB215F3927192181eBCD79227c70c10015Ff10df3",
        "0xB85485421d8a41C4648AB80bE1A725fA6b5Bc86d",
        "0xbB5c3B198f6def369bFB6AC7A34BB08eA49a0770",
        "0xC91223F844772dCdc2c6394585C8c30B3c1BE5C0",
        "0xCE3F076D0ADa9f913a24F42dEAB82e4b851B87d6",
        "0xdd3201eDfE43ae9B26aA847E7f194f1B6EE50778",
        "0xe38f71fc2Ca5f5761cE21F39Fff2cE70662FA54c",
        "0xf960AbF9ccC883970BEa3E79f65027E27278e1A5",
        "0xfcBe0B695c13257bd43D64f09Db433034E90033D",
        "0x2F375Ce83EE85e505150d24E85A1742fd03cA593",
        "0x4770F3186225b1A6879983BD88C669CA55463886",
        "0x8A801C334ebaC763822a0D85a595AeC6Da59C232",
        "0x92Aeed8027735C41605577b45A69429Bd7f729f9",
        "0xc136Eb8Abc892723aE87F355d12Cb721C4324D54",
        "0xc68bCEE3604F163f183Cf8B9a26E610E5961b037",
        "0xD6619A3E925472a8d7822Cc6A49B76b3554A3498",
        "0x05bAdF8A8e7fE5b43fae112108E26f2f663Bf1a2",
        "0x594DaaD7D77592a2b97b725A7AD59D7E188b5bFa",
        "0x927402ab67c0CDA3c187E9DFE34554AC581441f2",
        "0x1f186De364a56e741Fcb188d37a393d409D08AeA",
        "0x4E51960bd33A6edA71a8B24A76311834BD98DD9f",
        "0x84F7D2f6FB447Bb11d3E7Ce64D83e1c02c2F3078",
        "0xa0CCdBCeB5Da30F9d62F7A727F2B35C69dF08760",
        "0xE8ED1fca5af1c7dd46A3D5bbDFf7e99749D9e0aa",
        "0x3EF9181c9b96BAAafb3717A553E808Ccc72be37D",
    },
    Network.Arbitrum: {
        "0x89b0f9dB18FD079063cFA91F174B300C1ce0003C", # AIELON
    },
}

def customize_eth_portfolio() -> None:
    for token in skip_tokens.get(chain.id, []):
        eth_portfolio.SHITCOINS[chain.id].add(token)


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
