import logging
from functools import cached_property

from brownie import Contract
from cachetools.func import lru_cache, ttl_cache

from yearn.events import decode_logs, get_logs_asap
from yearn.utils import Singleton

logger = logging.getLogger(__name__)

DENOMINATIONS = {
    'ETH': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
    'BTC': '0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB',
    'USD': '0x0000000000000000000000000000000000000348',
}
ADDITIONAL_FEEDS = {
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",  # wbtc -> btc
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # weth -> eth
    "0xdB25f211AB05b1c97D595516F45794528a807ad8": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurs -> eur
    "0xC581b735A1688071A1746c968e0798D642EDE491": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # eurt -> eur
    "0xD71eCFF9342A5Ced620049e616c5035F1dB98620": "0xb49f677943BC038e9857d61E7d053CaA2C1734C1",  # seur -> eur
    "0x95dFDC8161832e4fF7816aC4B6367CE201538253": "0x01435677fb11763550905594a16b645847c1d0f3",  # ibkrw -> krw
}

SCALE = 10 ** 8


class Chainlink(metaclass=Singleton):
    def __init__(self):
        self.feeds = {}

    @cached_property
    def registry(self):
        # https://docs.chain.link/docs/feed-registry/#contract-addresses
        return Contract('0x47Fb2585D2C56Fe188D0E6ec628a38b74fCeeeDf')

    def load_feeds(self):
        if self.feeds:
            return
        logs = decode_logs(get_logs_asap(str(self.registry), [self.registry.topics['FeedConfirmed']]))
        self.feeds = {
            log['asset']: log['latestAggregator'] for log in logs if log['denomination'] == DENOMINATIONS['USD']
        }
        self.feeds.update(ADDITIONAL_FEEDS)
        logger.info(f'loaded {len(self.feeds)} feeds')

    @lru_cache(maxsize=None)
    def get_feed(self, asset):
        self.load_feeds()
        return Contract(self.feeds[asset])

    def __contains__(self, asset):
        self.load_feeds()
        return asset in self.feeds

    def get_price(self, asset, block=None):
        return self.get_feed(asset).latestAnswer(block_identifier=block) / SCALE


chainlink = Chainlink()


@ttl_cache(ttl=600)
def get_price(asset, block=None):
    try:
        return chainlink.get_price(asset, block)
    except (KeyError, ValueError):
        return None
