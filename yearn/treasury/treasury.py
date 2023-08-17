
import asyncio
import logging
from typing import Dict, List, Optional

from brownie import chain
from eth_portfolio import Portfolio
from eth_portfolio.buckets import get_token_bucket
from eth_portfolio.typing import Balance, RemoteTokenBalances, TokenBalances
from y.classes.common import ERC20
from y.exceptions import NonStandardERC20
from y.networks import Network

from yearn.constants import STRATEGIST_MULTISIG, TREASURY_WALLETS
from yearn.outputs.victoria.victoria import _build_item

logger = logging.getLogger(__name__)


async def _get_symbol(token):
    if token == 'ETH':
        return 'ETH'
    try:
        return await ERC20(token, asynchronous=True).symbol
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

    # TODO link this in
    async def partners_debt(self, block: int = None) -> dict:
        for i, partner in enumerate(partners):
            if i == 1:
                flat_wrappers = []
                for wrapper in partner.wrappers:
                    if isinstance(wrapper, Wrapper):
                        flat_wrappers.append(wrapper)
                    elif isinstance(wrapper, WildcardWrapper):
                        flat_wrappers.extend(await wrapper.unwrap())
                for wrapper in flat_wrappers:
                    print(wrapper.protocol_fees(block=block))

    # TODO:
    # def bonded_kp3r(self, block=None) -> dict:


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
