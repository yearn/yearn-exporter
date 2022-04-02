import logging

from brownie import ZERO_ADDRESS, chain
from cachetools.func import ttl_cache
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
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
    # https://docs.chain.link/docs/fantom-price-feeds/
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
    # feeds are hardcoded since there is no feed registry on Avalanche yet
    # https://docs.chain.link/docs/avalanche-price-feeds/
    Network.Avalanche: {
        "0x49d5c2bdffac6ce2bfdb6640f4f80f226bc10bab": "0x976B3D034E162d8bD72D6b9C989d545b839003b0", # WETH
        "0x50b7545627a5162f82a992c33b87adc75187b218": "0x2779D32d5166BAaa2B2b658333bA7e6Ec0C65743", # WBTC
        "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e": "0xF096872672F44d6EBA71458D74fe67F9a77a23B9", # USDC
        "0x63a72806098Bd3D9520cC43356dD78afe5D386D9": "0x3CA13391E9fb38a75330fb28f8cc2eB3D9ceceED", # AAVE
        "0x325a98F258a5732c7b06555603F6aF5BC1C17F0a": "0x7B0ca9A6D03FE0467A31Ca850f5bcA51e027B3aF", # ALPHA
        "0x027dbcA046ca156De9622cD1e2D907d375e53aa7": "0xcf667FB6Bd30c520A435391c50caDcDe15e5e12f", # AMPL
        "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7": "0x0A77230d17318075983913bC2145DB16C7366156", # wAVAX
        "0x19860CCB0A68fd4213aB9D8266F7bBf05A8dDe98": "0x827f8a0dC5c943F7524Dda178E2e7F275AAd743f", # BUSD
        "0x98a4d09036Cc5337810096b1D004109686E56Afc": "0x79bD0EDd79dB586F22fF300B602E85a662fc1208", # CAKE
        "0x249848BeCA43aC405b8102Ec90Dd5F22CA513c06": "0x7CF8A6090A9053B01F3DF4D4e6CfEdd8c90d9027", # CRV
        "0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE": "0x2854Ca10a54800e15A2a25cFa52567166434Ff0a", # sAVAX
        "0xd586E7F844cEa2F87f50152665BCbc2C279D8d70": "0x51D7180edA2260cc4F6e4EebB82FEF5c3c2B8300", # DAI
        "0xD24C2Ad096400B6FBcd2ad8B24E7acBc21A1da64": "0xbBa56eF1565354217a3353a466edB82E8F25b08e", # FRAX
        "0x214DB107654fF987AD859F34125307783fC8e387": "0x12Af94c3716bbf339Aa26BfD927DDdE63B27D50C", # FXS
        "0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd": "0x02D35d3a8aC3e1626d3eE09A78Dd87286F5E8e3a", # JOE
        "0x5947BB275c521040051D82396192181b413227A3": "0x49ccd9ca821EfEab2b98c60dC60F518E765EDe9a", # LINK
        "0x70928E5B188def72817b7775F0BF6325968e563B": "0x12Fe6A4DF310d4aD9887D27D4fce45a6494D4a4a", # LUNA
        "0x130966628846BFd36ff31a822705796e8cb8C18D": "0x54EdAB30a7134A16a54218AE64C73e1DAf48a8Fb", # MIM
        "0x3B55E45fD6bd7d4724F5c47E0d1bCaEdd059263e": "0x5D1F504211c17365CA66353442a74D4435A8b778", # MIMATIC
        "0x8729438EB15e2C8B576fCc6AeCdA6A148776C0F5": "0x36E039e6391A5E7A7267650979fdf613f659be5D", # QI
        "0xCE1bFFBD5374Dac86a2893119683F4911a2F7814": "0x4F3ddF9378a4865cf4f28BE51E10AECb83B7daeE", # SPELL
        "0x37B608519F91f70F2EeB0e5Ed9AF4061722e4F76": "0x449A373A090d8A1e5F74c63Ef831Ceff39E94563", # SUSHI
        "0x1C20E891Bab6b1727d14Da358FAe2984Ed9B59EB": "0x9Cf3Ef104A973b351B2c032AA6793c3A6F76b448", # TUSD
        "0x8eBAf22B6F053dFFeaf46f4Dd9eFA95D89ba8580": "0x9a1372f9b1B71B3A5a72E092AE67E172dBd7Daaa", # UNI
        "0xc7198437980c041c805A1EDcbA50c1Ce5db95118": "0xEBE676ee90Fe1112671f19b6B7459bC678B67e8a", # USDT
        "0xb599c3590F42f8F995ECfa0f85D2980B76862fc1": "0xf58B78581c480caFf667C63feDd564eCF01Ef86b", # UST
        "0xd1c3f94DE7e5B45fa4eDBBA472491a9f4B166FC4": "0x4Cf57DC9028187b9DAaF773c8ecA941036989238", # XAVA
        "0x9eAaC1B23d935365bD7b542Fe22cEEe2922f52dc": "0x28043B1Ebd41860B93EC1F1eC19560760B6dB556", # YFI
    }
}
registries = {
    # https://docs.chain.link/docs/feed-registry/#contract-addresses
    Network.Mainnet: '0x47Fb2585D2C56Fe188D0E6ec628a38b74fCeeeDf',
    Network.Fantom: None,
    Network.Avalanche: None,
}


class Chainlink(metaclass=Singleton):
    def __init__(self):
        if chain.id not in registries:
            raise UnsupportedNetwork('chainlink is not supported on this network')

        if registries[chain.id]:
            self.registry = contract(registries[chain.id])
            self.load_feeds()
        else:
            self.feeds = ADDITIONAL_FEEDS[chain.id]

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
