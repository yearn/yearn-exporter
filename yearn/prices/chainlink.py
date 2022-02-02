import logging
from functools import cached_property

from brownie import chain, ZERO_ADDRESS
from cachetools.func import lru_cache, ttl_cache

from yearn.events import decode_logs, get_logs_asap
from yearn.utils import Singleton, contract
from yearn.networks import Network
from yearn.exceptions import UnsupportedNetwork

logger = logging.getLogger(__name__)

DENOMINATIONS = {
    'ETH': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
    'BTC': '0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB',
    'USD': '0x0000000000000000000000000000000000000348',
}
ADDITIONAL_FEEDS = {
    Network.Mainnet: {
        "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",  # wbtc -> btc
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # weth -> eth
        "0x0100546F2cD4C9D97f798fFC9755E47865FF7Ee6": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # aleth -> eth
        "0xdB25f211AB05b1c97D595516F45794528a807ad8": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurs -> eur
        "0xC581b735A1688071A1746c968e0798D642EDE491": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurt -> eur
        "0xD71eCFF9342A5Ced620049e616c5035F1dB98620": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # seur -> eur
        "0x81d66D255D47662b6B16f3C5bbfBb15283B05BC2": "0x438F81D95761d7036cd2617295827D9d01Cf593f",  # ibzar -> zar
    },
    # https://data.chain.link/fantom/mainnet
    Network.Fantom: {
        "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83": "0xf4766552D15AE4d256Ad41B6cf2933482B0680dc", # wftm  -> usd
        "0x321162Cd933E2Be498Cd2267a90534A804051b11": "0x321162Cd933E2Be498Cd2267a90534A804051b11", # wbtc  -> usd
        "0x74b23882a30290451A17c44f4F05243b6b58C76d": "0x11DdD3d147E5b83D01cee7070027092397d63658", # weth  -> usd
        "0xd6070ae98b8069de6B494332d1A1a81B6179D960": "0x4F5Cc6a2291c964dEc4C7d6a50c0D89492d4D91B", # bifi  -> usd
        "0x1E4F97b9f9F913c46F1632781732927B9019C68b": "0xa141D7E3B44594cc65142AE5F2C7844Abea66D2B", # crv   -> usd
        "0x6a07A792ab2965C72a5B8088d3a069A7aC3a993B": "0xE6ecF7d2361B6459cBb3b4fb065E0eF4B175Fe74", # aave  -> usd
        "0x657A1861c15A3deD9AF0B6799a195a249ebdCbc6": "0xD2fFcCfA0934caFdA647c5Ff8e7918A10103c01c", # cream -> usd
        "0xb3654dc3D10Ea7645f8319668E8F54d2574FBdC8": "0x221C773d8647BC3034e91a0c47062e26D20d97B4", # link  -> usd
        "0x399fe752D39338d28C36F3370fbebd8292fb9E6e": "0xb26867105D25bD127862bEA9B952Fa2E89942837", # ohmv2 -> usd
        "0x56ee926bD8c72B2d5fa1aF4d9E4Cbb515a1E3Adc": "0x2Eb00cC9dB7A7E0a013A49b3F6Ac66008d1456F7", # snx   -> usd
        "0x468003B688943977e6130F4F68F23aad939a1040": "0x02E48946849e0BFDD7bEa5daa80AF77195C7E24c", # spell -> usd
        "0xae75A438b2E0cB8Bb01Ec1E1e376De11D44477CC": "0xCcc059a1a17577676c8673952Dc02070D29e5a66", # sushi -> usd
        "0x81740D647493a61329E1c574A11ee7577659fb14": "0x4be9c8fb4105380116c03fc2eeb9ea1e1a109d95", # fchf  -> usd
        "0xe105621721D1293c27be7718e041a4Ce0EbB227E": "0x3E68e68ea2c3698400465e3104843597690ae0f7", # feur  -> usd
        "0x29b0Da86e484E1C0029B56e817912d778aC0EC69": "0x9B25eC3d6acfF665DfbbFD68B3C1D896E067F0ae", # yfi   -> usd
    }
}
registries = {
    # https://docs.chain.link/docs/feed-registry/#contract-addresses
    Network.Mainnet: '0x47Fb2585D2C56Fe188D0E6ec628a38b74fCeeeDf',
    Network.Fantom: ZERO_ADDRESS,
}

class Chainlink(metaclass=Singleton):
    def __init__(self):
        if chain.id not in registries:
            raise UnsupportedNetwork('chainlink is not supported on this network')

        if registries[chain.id] == ZERO_ADDRESS:
            self.feeds = ADDITIONAL_FEEDS[chain.id]
        else:
            self.registry = contract(registries[chain.id])
            self.load_feeds()

    def load_feeds(self):
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

    def get_feed(self, asset):
        return contract(self.feeds[asset])

    def __contains__(self, asset):
        return asset in self.feeds

    @ttl_cache(maxsize=None, ttl=600)
    def get_price(self, asset, block=None):
        if asset == ZERO_ADDRESS:
            return None
        try:
            return self.get_feed(asset).latestAnswer(block_identifier=block) / 1e8
        except ValueError:
            return None

chainlink = None
try:
    chainlink = Chainlink()
except UnsupportedNetwork:
    pass
