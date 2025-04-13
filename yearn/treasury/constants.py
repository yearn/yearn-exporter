
from y.constants import CHAINID
from y.networks import Network

from yearn.constants import YFI
from yearn.prices.constants import weth

# The buyback contract
BUYER = {
    Network.Mainnet: "0x6903223578806940bd3ff0C51f87aa43968424c8",
}.get(CHAINID, None)

YFI_LIKE = {
    Network.Mainnet: {
        YFI,
        '0xD0660cD418a64a1d44E9214ad8e459324D8157f1',  # WOOFY
    },
    Network.Fantom: {
        YFI,
        '0xD0660cD418a64a1d44E9214ad8e459324D8157f1',  # WOOFY
    },
}.get(CHAINID, set())

ETH_LIKE = {
    Network.Mainnet: {
        "ETH",
        weth,
        "0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb", # seth
        "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", # eth
        "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", # steth
        "0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593", # reth
        "0xE95A203B1a91a908F9B9CE46459d101078c2c3cb", # ankreth
    },
}.get(CHAINID, set())

BTC_LIKE = {
    Network.Mainnet: {
        "0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D", # renbtc
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", # wbtc
        "0xfE18be6b3Bd88A2D2A7f928d00292E7a9963CfC6", # sbtc
        "0x8064d9Ae6cDf087b1bcd5BDf3531bD5d8C537a68", # obtc
        "0x9BE89D2a4cd102D8Fecc6BF9dA793be995C22541", # bbtc
        "0x0316EB71485b0Ab14103307bf65a021042c6d380", # hbtc
        "0x5228a22e72ccC52d415EcFd199F99D0665E7733b", # pbtc
        "0x8dAEBADE922dF735c38C80C7eBD708Af50815fAa", # tbtc
    },
    Network.Fantom: {
        "0x321162Cd933E2Be498Cd2267a90534A804051b11", # wbtc
    },
}.get(CHAINID, set())

INTL_STABLECOINS = {
    Network.Mainnet: {
        '0xD71eCFF9342A5Ced620049e616c5035F1dB98620',  # sEUR
        '0xC581b735A1688071A1746c968e0798D642EDE491',  # EURT
        '0xdB25f211AB05b1c97D595516F45794528a807ad8',  # EURS
        '0x96E61422b6A9bA0e068B6c5ADd4fFaBC6a4aae27',  # ibEUR
        '0x95dFDC8161832e4fF7816aC4B6367CE201538253',  # ibKRW
        '0x69681f8fde45345C3870BCD5eaf4A05a60E7D227',  # ibGBP
        '0x1CC481cE2BD2EC7Bf67d1Be64d4878b16078F309',  # ibCHF
        '0x5555f75e3d5278082200Fb451D1b6bA946D8e13b',  # ibJPY
    },
    Network.Arbitrum: {
        '0xFa247d0D55a324ca19985577a2cDcFC383D87953',  # PHP Philippine Peso
    },
}.get(CHAINID, set())

OTHER_LONG_TERM_ASSETS = {
    # Non-YFI long term hodls
    Network.Mainnet: {
        '0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44',  # KP3R
        '0xaf988afF99d3d0cb870812C325C588D8D8CB7De8',  # SLP (KP3R/ETH)
    },
}.get(CHAINID, set())
