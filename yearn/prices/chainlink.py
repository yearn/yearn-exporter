import logging
from typing import Optional

from brownie import ZERO_ADDRESS, Contract, chain, convert
from brownie.exceptions import VirtualMachineError
from cachetools.func import ttl_cache

from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)

DENOMINATIONS = {
    'ETH': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
    'BTC': '0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB',
    'USD': '0x0000000000000000000000000000000000000348',
}
ADDITIONAL_FEEDS = {
    # map similar tokens to existing feeds
    Network.Mainnet: {
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",  # wbtc -> btc
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # weth -> eth
        "0x0100546F2cD4C9D97f798fFC9755E47865FF7Ee6": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # aleth -> eth
        "0xdB25f211AB05b1c97D595516F45794528a807ad8": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurs -> eur
        "0xC581b735A1688071A1746c968e0798D642EDE491": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurt -> eur
        "0xD71eCFF9342A5Ced620049e616c5035F1dB98620": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # seur -> eur
        "0x81d66D255D47662b6B16f3C5bbfBb15283B05BC2": "0x438F81D95761d7036cd2617295827D9d01Cf593f",  # ibzar -> zar
    },
    # feeds are hardcoded since there is no feed registry on fantom yet
    # https://data.chain.link/fantom/mainnet
    Network.Fantom: {
        "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83": "0xf4766552D15AE4d256Ad41B6cf2933482B0680dc",  # wftm
        "0x321162Cd933E2Be498Cd2267a90534A804051b11": "0x8e94C22142F4A64b99022ccDd994f4e9EC86E4B4",  # wbtc
        "0x2406dCe4dA5aB125A18295f4fB9FD36a0f7879A2": "0x8e94C22142F4A64b99022ccDd994f4e9EC86E4B4",  # anybtc
        "0x74b23882a30290451A17c44f4F05243b6b58C76d": "0x11DdD3d147E5b83D01cee7070027092397d63658",  # weth
        "0xBDC8fd437C489Ca3c6DA3B5a336D11532a532303": "0x11DdD3d147E5b83D01cee7070027092397d63658",  # anyeth
        "0xd6070ae98b8069de6B494332d1A1a81B6179D960": "0x4F5Cc6a2291c964dEc4C7d6a50c0D89492d4D91B",  # bifi
        "0x1E4F97b9f9F913c46F1632781732927B9019C68b": "0xa141D7E3B44594cc65142AE5F2C7844Abea66D2B",  # crv
        "0x6a07A792ab2965C72a5B8088d3a069A7aC3a993B": "0xE6ecF7d2361B6459cBb3b4fb065E0eF4B175Fe74",  # aave
        "0x657A1861c15A3deD9AF0B6799a195a249ebdCbc6": "0xD2fFcCfA0934caFdA647c5Ff8e7918A10103c01c",  # cream
        "0xb3654dc3D10Ea7645f8319668E8F54d2574FBdC8": "0x221C773d8647BC3034e91a0c47062e26D20d97B4",  # link
        "0x399fe752D39338d28C36F3370fbebd8292fb9E6e": "0xb26867105D25bD127862bEA9B952Fa2E89942837",  # ohmv2
        "0x56ee926bD8c72B2d5fa1aF4d9E4Cbb515a1E3Adc": "0x2Eb00cC9dB7A7E0a013A49b3F6Ac66008d1456F7",  # snx
        "0x468003B688943977e6130F4F68F23aad939a1040": "0x02E48946849e0BFDD7bEa5daa80AF77195C7E24c",  # spell
        "0xae75A438b2E0cB8Bb01Ec1E1e376De11D44477CC": "0xCcc059a1a17577676c8673952Dc02070D29e5a66",  # sushi
        "0x81740D647493a61329E1c574A11ee7577659fb14": "0x4be9c8fb4105380116c03fc2eeb9ea1e1a109d95",  # fchf
        "0xe105621721D1293c27be7718e041a4Ce0EbB227E": "0x3E68e68ea2c3698400465e3104843597690ae0f7",  # feur
        "0x29b0Da86e484E1C0029B56e817912d778aC0EC69": "0x9B25eC3d6acfF665DfbbFD68B3C1D896E067F0ae",  # yfi
    },

    Network.Gnosis: {
        "0x8e5bBbb09Ed1ebdE8674Cda39A0c169401db4252" : "0x6c1d7e76ef7304a40e8456ce883bc56d3dea3f7d", # wbtc
        "0x6A023CCd1ff6F2045C3309768eAd9E68F978f6e1" : "0xa767f745331d267c7751297d982b050c93985627", # weth
        "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83" : "0x26c31ac71010af62e6b486d1132e266d6298857d", # usdc
        "0x712b3d230F3C1c19db860d80619288b1F0BDd0Bd" : "0xc77b83ac3dd2a761073bd0f281f7b880b2ddde18", # crv
        "0xDF613aF6B44a31299E48131e9347F034347E2F00" : "0x2b481dc923aa050e009113dca8dcb0dab4b68cdf", # aave
        "0xE2e73A1c69ecF83F464EFCE6A5be353a37cA09b2" : "0xed322a5ac55bae091190dff9066760b86751947b", # link
        "0x3A00E08544d589E19a8e7D97D0294331341cdBF6" : "0x3b84d6e6976d5826500572600eb44f9f1753827b", # snx
        "0x2995D1317DcD4f0aB89f4AE60F3f020A4F17C7CE" : "0xc0a6bf8d5d408b091d022c3c0653d4056d4b9c01", # sushi
        "0x44fA8E6f47987339850636F88629646662444217" : "0x678df3415fc31947da4324ec63212874be5a82f8", # dai
        "0xbf65bfcb5da067446CeE6A706ba3Fe2fB1a9fdFd" : "0x14030d5a0c9e63d9606c6f2c8771fc95b34b07e0", # yfi
        "0x7f7440C5098462f833E123B44B8A03E1d9785BAb" : "0xfdf9eb5fafc11efa65f6fd144898da39a7920ae8", # 1inch
        "0xDf6FF92bfDC1e8bE45177DC1f4845d391D3ad8fD" : "0xba95bc8418ebcdf8a690924e1d4ad5292139f2ea", # comp
    },

    Network.Arbitrum: {
        "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f" : "0x6ce185860a4963106506C203335A2910413708e9", # wbtc
        "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1" : "0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612", # weth
        "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1" : "0xc5C8E77B397E531B8EC06BFb0048328B30E9eCfB", # dai
        "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9" : "0x3f3f5dF88dC9F13eac63DF89EC16ef6e7E25DdE7", # usdt
        "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8" : "0x50834F3163758fcC1Df9973b6e91f0F0F0434aD3", # usdc
        "0xFEa7a6a0B346362BF88A9e4A88416B77a57D6c2A" : "0x87121F6c9A9F6E90E59591E4Cf4804873f54A95b", # mim
        "0x82e3A8F066a6989666b031d916c43672085b1582" : "0x745Ab5b69E01E2BE1104Ca84937Bb71f96f5fB21", # yfi
    },

    Network.Optimism: {
        "0x68f180fcCe6836688e9084f035309E29Bf0A2095" : "0xD702DD976Fb76Fffc2D3963D037dfDae5b04E593", # wbtc
        "0x4200000000000000000000000000000000000006" : "0x13e3Ee699D1909E989722E753853AE30b17e08c5", # weth
        "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1" : "0x8dBa75e83DA73cc766A7e5a0ee71F656BAb470d6", # dai
        "0x4200000000000000000000000000000000000042" : "0x0D276FC14719f9292D5C1eA2198673d1f4269246", # op
        "0x2E3D870790dC77A83DD1d18184Acc7439A53f475" : "0xc7D132BeCAbE7Dcc4204841F33bae45841e41D9C", # frax
        "0x350a791Bfc2C21F9Ed5d10980Dad2e2638ffa7f6" : "0xCc232dcFAAE6354cE191Bd574108c1aD03f86450", # link
        "0x7F5c764cBc14f9669B88837ca1490cCa17c31607" : "0x16a9FA2FDa030272Ce99B29CF780dFA30361E0f3", # usdc
        "0x8700dAec35aF8Ff88c16BdF0418774CB3D7599B4" : "0x2FCF37343e916eAEd1f1DdaaF84458a359b53877", # snx
    }

}
registries = {
    # https://docs.chain.link/docs/feed-registry/#contract-addresses
    Network.Mainnet: '0x47Fb2585D2C56Fe188D0E6ec628a38b74fCeeeDf',
    Network.Fantom: None,
    Network.Gnosis: None,
    Network.Arbitrum: None,
    Network.Optimism: None,
}


class Chainlink(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in registries:
            raise UnsupportedNetwork('chainlink is not supported on this network')

        if registries[chain.id]:
            self.registry = contract(registries[chain.id])
            self.load_feeds()
        else:
            self.feeds = ADDITIONAL_FEEDS[chain.id]

    def load_feeds(self) -> None:
        logs = decode_logs(
            get_logs_asap(str(self.registry), [self.registry.topics['FeedConfirmed']])
        )
        self.feeds = {
            log['asset']: log['latestAggregator']
            for log in logs
            if log['denomination'] == DENOMINATIONS['USD']
        }
        self.feeds.update(ADDITIONAL_FEEDS[chain.id])
        logger.info(f'loaded {len(self.feeds)} feeds')

    def get_feed(self, asset: AddressOrContract) -> Contract:
        return contract(self.feeds[convert.to_address(asset)])

    def __contains__(self, asset: AddressOrContract) -> bool:
        return convert.to_address(asset) in self.feeds

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, asset: AddressOrContract, block: Optional[Block] = None) -> Optional[float]:
        if asset == ZERO_ADDRESS:
            return None
        try:
            price = self.get_feed(convert.to_address(asset)).latestAnswer(block_identifier=block) / 1e8
            # latestAnswer can return 0 before the feed is in use
            if price:
                return price
        except (ValueError, VirtualMachineError):
            return None


chainlink = None
try:
    chainlink = Chainlink()
except UnsupportedNetwork:
    pass
