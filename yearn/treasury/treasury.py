
import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Set

from brownie import chain, web3
from brownie.convert.datatypes import EthAddress
from brownie.network.event import EventDict
from eth_abi import encode_single
from eth_portfolio import Portfolio
from eth_portfolio.buckets import get_token_bucket
from eth_portfolio.typing import Balance, RemoteTokenBalances, TokenBalances
from eth_utils import encode_hex
from y.classes.common import ERC20
#from yearn.partners.partners import partners
#from yearn.partners.snapshot import WildcardWrapper, Wrapper
#from yearn.prices import compound
#from yearn.prices.constants import weth
#from yearn.prices.magic import _describe_err
from y.exceptions import NonStandardERC20
from yearn.constants import (ERC20_TRANSFER_EVENT_HASH,
                             ERC677_TRANSFER_EVENT_HASH, STRATEGIST_MULTISIG,
                             TREASURY_WALLETS)
from yearn.decorators import sentry_catch_all, wait_or_exit_after
from yearn.networks import Network
from yearn.outputs.victoria.victoria import _build_item
from yearn.utils import contract

logger = logging.getLogger(__name__)


NFTS = [
    # These are NFTs # TODO 
    '0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85', # ENS domains
    '0x01234567bac6fF94d7E4f0EE23119CF848F93245', # EthBlocks
    '0xD7aBCFd05a9ba3ACbc164624402fB2E95eC41be6', # EthJuanchos
    '0xeF81c2C98cb9718003A89908e6bd1a5fA8A098A3', # SpaceShiba
    '0xD1E5b0FF1287aA9f9A268759062E4Ab08b9Dacbe', # .crypto Domain
    '0x437a6B880d4b3Be9ed93BD66D6B7f872fc0f5b5E', # Soda
    '0x9d45DAb69f1309F1F55A7280b1f6a2699ec918E8', # yFamily 2021
]

# The exporter will completely ignore transfers from the following contract addresses:
SKIP_LOGS = {
    Network.Mainnet: [
        # Spam:
        '0x0734E85525Ca6838fe48EC6EB29b9d457F254F73', # SOLID spam
        '0x3B6e5fA0322888b94DCA443cE4F3785ac0001DFA', # SOLID spam
        '0x459176FDC68C945B6bb23eB946eee62457041567', # SOLID spam
        '0x4709099BE25D156578405132d66aeBfC2e12937A', # SOLID spam
        '0x698068C6a369b1BF04D516f5fE48424797973DCf', # SOLID spam
        '0x7cfa05320D83A20980Ac76B91a3A11981877Ef3A', # SOLID spam
        '0x84d12988D71244a8937a9816037BeB3e61E17FdD', # SOLID spam
        '0x875bf9be244970B8572DD042053508bF758371Ee', # SOLID spam
        '0x908599FDf490b73D171B57731bd4Ca95b7F0DE6a', # SOLID spam
        '0xa10c97bF5629340A35c41a8AA308af0804750605', # SOLID spam
        '0xf8358bd95dcA48187e3F4BE05847F3593776C086', # SOLID spam
        "0x26004d228fC8A32c5bd1a106108c8647A455B04a", # RSwap spam
        '0x1412ECa9dc7daEf60451e3155bB8Dbf9DA349933', # A68 spam
        '0xa9517B2E61a57350D6555665292dBC632C76adFe', # long name spam
        '0xb07de4b2989E180F8907B8C7e617637C26cE2776', # long name spam
        '0x830Cbe766EE470B67F77ea62a56246863F75f376', # ILH spam
        '0x2B000332CD291eF558aF76298A4d6F6001E4e015', # XAR spam
        '0x6A007E207E50B4C6B2ADCFc6a873F6e698645fE3', # LENS spam
        '0x4ab16CDc82a4eA4727Ab40caee1bb46622C13641', # fake SABLIER clone spam
        '0x9D79d5B61De59D882ce90125b18F74af650acB93', # NBST token with erroneous price
        # Other:
        '0x1BA4b447d0dF64DA64024e5Ec47dA94458C1e97f', # Hegic Option Token from strategist testing, expired and worthless
        '0xeaaa790591c646b0436f02f63e8Ca56209FEDE4E', # DHR D-Horse token
        '0x1e988ba4692e52Bc50b375bcC8585b95c48AaD77', # BBB Bufficorn Buidl Brigade
    ],
    Network.Fantom: [
        "0x630277E37fd2Ddf81e4683f3692dD817aa6225Cb", # 8bitcats
    ]
}.get(chain.id,[])


class Treasury:
    '''
    Used to export financial reports
    '''

    def __init__(self, label: str, wallets: Set[EthAddress], watch_events_forever: bool = False, start_block: int = 0) -> None:
        self.label = label
        self.addresses = list(wallets)
        self._start_block = start_block
        self._transfers = []

        # define transfer signatures for Transfer events from ERC-20 and ERC-677 contracts
        transfer_sigs = [
            ERC20_TRANSFER_EVENT_HASH,
            ERC677_TRANSFER_EVENT_HASH
        ]
        treasury_addresses = [encode_hex(encode_single('address', address)) for address in self.addresses]
        self._topics = [
            [
                transfer_sigs,
                None,
                treasury_addresses # Transfers into Treasury wallets
            ],
            [
                transfer_sigs,
                treasury_addresses # Transfers out of Treasury wallets
            ]
        ]
        self._watch_events_forever = watch_events_forever
        self._done = threading.Event()
        self._has_exception = False
        self._thread = threading.Thread(target=self.watch_transfers, daemon=True)
    
    @property
    def transfers(self) -> List[EventDict]:
        self.load_transfers()
        return self._transfers

    # descriptive functions
    # assets

    # helper functions
    @wait_or_exit_after
    def load_transfers(self) -> None:
        if not self._thread._started.is_set():
            self._thread.start()

    @sentry_catch_all
    def watch_transfers(self) -> None:
        start = time.time()
        logger.info(
            'pulling treasury transfer events, please wait patiently this takes a while...'
        )
        transfer_filters = [
            web3.eth.filter({"fromBlock": self._start_block, "topics": topics})
            for topics in self._topics
        ]

        transfer_logs = [transfer_filter.get_all_entries() for transfer_filter in transfer_filters]

        while True:
            for logs in transfer_logs:
                self.process_transfers(logs)

            if not self._done.is_set():
                self._done.set()
                logger.info(
                    f"loaded {self.label} transfer events in %.3fs", time.time() - start
                )
            if not self._watch_events_forever:
                return

            time.sleep(5)

            # read new logs at end of loop
            transfer_logs = [transfer_filter.get_new_entries() for transfer_filter in transfer_filters]


    # export functions

async def _get_symbol(token):
    if token == 'ETH':
        return 'ETH'
    try:
        return await ERC20(token).symbol_async
    except NonStandardERC20:
        return None

class ExportablePortfolio(Portfolio):
    """ Adds methods to export full portoflio data. """ 

    async def data_for_export(self, block, ts) -> List[Dict]:
        metrics_to_export = []
        data = await self.describe(block)

        for wallet, wallet_data in data.items():
            for section, section_data in wallet_data.items():
                if isinstance(section_data, TokenBalances):
                    for token, bals in section_data.items():
                        if items := await self._process_token(ts, section, wallet, token, bals):
                            metrics_to_export.extend(items)
                elif isinstance(section_data, RemoteTokenBalances):
                    if section == 'external':
                        section = 'assets'
                    for protocol, token_bals in section_data.items():
                        for token, bals in token_bals.items():
                            if items := await self._process_token(ts, section, wallet, token, bals, protocol=protocol):
                                metrics_to_export.extend(items)
                else:
                    raise NotImplementedError()

        return metrics_to_export
    
    async def _process_token(self, ts, section: str, wallet: str, token: str, bals: Balance, protocol: Optional[str] = None):
        # TODO wallet nicknames in grafana
        #wallet = KNOWN_ADDRESSES[wallet] if wallet in KNOWN_ADDRESSES else wallet
        if protocol is not None:
            wallet = f'{protocol} | {wallet}'

        symbol, bucket = await asyncio.gather(
            _get_symbol(token),
            get_token_bucket(token),
        )
        
        items = []           

        # build items
        for key, value in bals.items():
            label_names = ['param','wallet','token_address','token','bucket']
            if key == "usd_value":
                key = "usd value"
            label_values = [key, wallet, token, symbol, bucket]
            items.append(_build_item(f"{self.label}_{section}", label_names, label_values, value, ts))
        return items


class YearnTreasury(ExportablePortfolio):
    def __init__(self, asynchronous: bool = False, load_prices: bool = False) -> None:
        start_block = {
            Network.Mainnet: 10_502_337,
            Network.Fantom: 18_950_072,
            Network.Gnosis: 20_000_000,
            Network.Arbitrum: 4_837_859,
            Network.Optimism: 18_100_336,
        }[chain.id]
        
        ''' TODO: confirm these starts match start_block
        start = {
            Network.Mainnet: datetime(2020, 7, 21, 10, 1, tzinfo=timezone.utc), # first treasury tx
            Network.Fantom: datetime(2021, 10, 12, tzinfo=timezone.utc), # Fantom Multisig deployed
            Network.Gnosis: datetime(2022, 1, 8, 2, 20, 50, tzinfo=timezone.utc), # Block 20_000_000, some time near the first tx in the Gnosis treasury EOA. Further testing is needed to confirm as first tx was not fully apparent on block explorer.
            Network.Arbitrum: datetime(2022, 1, 20, 23, 10, tzinfo=timezone.utc), # first treasury tx time block 4837859
            Network.Optimism: datetime(2022, 8, 6, 20, 1, 18, tzinfo=timezone.utc), # create contract blocks 18100336
        }[chain.id]
        '''
        super().__init__(TREASURY_WALLETS, label='treasury', start_block=start_block, asynchronous=asynchronous, load_prices=load_prices)

    def partners_debt(self, block: int = None) -> dict:
        for i, partner in enumerate(partners):
            if i == 1:
                flat_wrappers = []
                for wrapper in partner.wrappers:
                    if isinstance(wrapper, Wrapper):
                        flat_wrappers.append(wrapper)
                    elif isinstance(wrapper, WildcardWrapper):
                        flat_wrappers.extend(wrapper.unwrap())
                for wrapper in flat_wrappers:
                    print(wrapper.protocol_fees(block=block))

    # def bonded_kp3r(self, block=None) -> dict:

    # def debt - expends super().debt

class StrategistMultisig(ExportablePortfolio):
    def __init__(self, asynchronous: bool = False, load_prices: bool = False) -> None:
        start_block = {
            Network.Mainnet: 11_507_716,
            Network.Fantom: 10_836_306,
            Network.Gnosis: 20_455_212,
            Network.Arbitrum: 2_434_174,
            Network.Optimism: 18_084_577,
        }[chain.id]
        super().__init__(STRATEGIST_MULTISIG, label='sms', start_block=start_block, asynchronous=asynchronous, load_prices=load_prices)

        """ TODO check these
        start = {
            Network.Mainnet: datetime(2021, 1, 28, 9, 10, tzinfo=timezone.utc), # first inbound sms tx
            Network.Fantom: datetime(2021, 6, 17, tzinfo=timezone.utc), # Fantom SMS deployed
            Network.Gnosis: datetime(2022, 2, 3, 23, 45, tzinfo=timezone.utc), # Block 20455212, first tx in SMS
            Network.Arbitrum: datetime(2021, 10, 21, 21, 20, tzinfo=timezone.utc), # block 2434174, first trx
            Network.Optimism: datetime(2022, 8, 6, 17, 27, 45, tzinfo=timezone.utc), # block 18084577
        }[chain.id]
        """
