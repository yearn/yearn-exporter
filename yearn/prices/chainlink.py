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
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",  # wbtc -> btc
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # weth -> eth
    "0x0100546F2cD4C9D97f798fFC9755E47865FF7Ee6": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # aleth -> eth
    "0xdB25f211AB05b1c97D595516F45794528a807ad8": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurs -> eur
    "0xC581b735A1688071A1746c968e0798D642EDE491": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurt -> eur
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # seur -> eur
    "0x81d66D255D47662b6B16f3C5bbfBb15283B05BC2": "0x438F81D95761d7036cd2617295827D9d01Cf593f",  # ibzar -> zar
}
registries = {
    # https://docs.chain.link/docs/feed-registry/#contract-addresses
    Network.Mainnet: '0x47Fb2585D2C56Fe188D0E6ec628a38b74fCeeeDf',
}


class Chainlink(metaclass=Singleton):
    def __init__(self):
        if chain.id not in registries:
            raise UnsupportedNetwork('chainlink is not supported on this network')

        self.registry = contract(registries[chain.id])
        self.load_feeds()

    def __repr__(self):
        return "chainlink"

    def load_feeds(self):
        logs = decode_logs(
            get_logs_asap(str(self.registry), [self.registry.topics['FeedConfirmed']])
        )
        self.feeds = {
            log['asset']: log['latestAggregator']
            for log in logs
            if log['denomination'] == DENOMINATIONS['USD']
        }
        self.feeds.update(ADDITIONAL_FEEDS)
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
        except (ValueError, KeyError):
            return None


chainlink = None
try:
    chainlink = Chainlink()
except UnsupportedNetwork:
    pass
