from functools import lru_cache
import logging
import threading
import time
from typing import Dict, List, Optional, Set

from brownie import ZERO_ADDRESS, chain, web3
from brownie.convert.datatypes import EthAddress
from brownie.network.event import EventDict, EventLookupError, _EventItem
from eth_abi import encode_single
from eth_utils import encode_hex
from joblib import Parallel, delayed
from yearn.constants import (ERC20_TRANSFER_EVENT_HASH,
                             ERC677_TRANSFER_EVENT_HASH, STRATEGIST_MULTISIG,
                             TREASURY_WALLETS)
from yearn.decorators import sentry_catch_all, wait_or_exit_after
from yearn.events import decode_logs
from yearn.exceptions import PriceError
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.outputs.victoria import output_treasury
from yearn.partners.partners import partners
from yearn.partners.snapshot import WildcardWrapper, Wrapper
from yearn.prices import compound
from yearn.prices.constants import weth
from yearn.prices.magic import _describe_err, get_price
from yearn.prices.magic import logger as logger_price_magic
from yearn.typing import Block
from yearn.utils import contract

logger = logging.getLogger(__name__)
logger_price_magic.setLevel(logging.CRITICAL)


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

def _get_price(token: EthAddress, block: int = None) -> float:
    SKIP_PRICE = [  # shitcoins
        "0xa9517B2E61a57350D6555665292dBC632C76adFe",
        "0xb07de4b2989E180F8907B8C7e617637C26cE2776",
        "0x1368452Bfb5Cd127971C8DE22C58fBE89D35A6BF",
        "0x5cB5e2d7Ab9Fd32021dF8F1D3E5269bD437Ec3Bf",
        "0x11068577AE36897fFaB0024F010247B9129459E6",
        "0x9694EED198C1b7aB81ADdaf36255Ea58acf13Fab",
        "0x830Cbe766EE470B67F77ea62a56246863F75f376",
        "0x8F49cB69ee13974D6396FC26B0c0D78044FCb3A7",
        "0x53d345839E7dF5a6c8Cf590C5c703AE255E44816",
        "0xcdBb37f84bf94492b44e26d1F990285401e5423e",
        "0xE256CF1C7caEff4383DabafEe6Dd53910F97213D",
        "0x528Ff33Bf5bf96B5392c10bc4748d9E9Fb5386B2",
    ]
    if token in SKIP_PRICE:
        return 0
    try:
        return get_price(token, block, return_price_during_vault_downtime=True)
    except PriceError:
        desc_str = _describe_err(token, block)
        if desc_str.startswith('yv'):
            raise
        logger.critical(f'PriceError while fetching price for {desc_str}')
    except (AttributeError,ValueError) as e:
        desc_str = _describe_err(token, block)
        if desc_str.startswith('yv'):
            raise
        logger.critical(f'{type(e).__name__} while fetching price for {desc_str} | {e}')
    return 0


def get_token_from_event(event: _EventItem) -> EthAddress:
    try:
        transfer = event['Transfer']
        address = transfer[0].address
        # try to download the contract from etherscan
        contract(address)
        return address
    except ValueError:
        # some tokens have unverified sources with etherscan, skip them!
        return None
    except EventLookupError:
        logger.critical(event)
        try:
            logger.critical(
                f'One of your cached contracts has an incorrect definition: {event.address}. Please fix this manually'
            )
        except AttributeError:
            address = event["(unknown)"][0].address
            if address is None:
                logger.critical("event.address is None")
                return
            logger.critical(
                f'One of your cached contracts has an incorrect definition: {address}. Please fix this manually'
            )
        raise


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

    def assets(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        assets = self.held_assets(block=block)
        assets.update(self.collateral(block=block))
        return assets

    def token_list(self, address: EthAddress, block: int = None) -> List[EthAddress]:
        tokens = set()
        for event in self.transfers:
            token = get_token_from_event(event)
            if token is None:
                continue

            transfer = event['Transfer']
            if transfer.values()[1] == address:
                if block:
                    if transfer[0].block_number <= block:
                        tokens.add(token)
                else:
                    tokens.add(token)

        return list(tokens)


    def held_assets(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        balances = {}
        for address in self.addresses:
            # get token balances
            tokens = self.token_list(address, block=block)
            token_balances = fetch_multicall(
                *[[contract(token), "balanceOf", address] for token in tokens],
                block=block,
            )
            decimals = fetch_multicall(
                *[[contract(token), "decimals"] for token in tokens],
                block=block,
                require_success=False
            )
            token_balances = [
                balance / 10 ** decimal if decimal else balance
                for balance, decimal in zip(token_balances, decimals)
            ]
            token_prices = Parallel(8, 'threading')(
                delayed(_get_price)(token, block) for token in tokens
            )
            token_balances = [
                {'balance': balance, 'usd value': balance * price}
                for balance, price in zip(token_balances, token_prices)
            ]
            balances[address] = dict(zip(tokens, token_balances))

            # then, add eth
            if block:
                balance = (
                    web3.eth.get_balance(address, block_identifier=block) / 10 ** 18
                )
            else:
                balance = web3.eth.get_balance(address) / 10 ** 18
            balances[address]['ETH'] = {
                'balance': balance,
                'usd value': balance * get_price(weth, block),
            }
        return balances

    def collateral(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        collateral = {}

        maker_collateral = self.maker_collateral(block=block)
        if maker_collateral:
            for address, data in maker_collateral.items():
                collateral[f'{address} Maker CDP'] = data

        unit_collateral = self.unit_collateral(block=block)
        if unit_collateral:
            for address, data in unit_collateral.items():
                collateral[f'{address} Unit CDP'] = data

        collateral = {key: value for key, value in collateral.items() if len(value)}
        return collateral

    def maker_collateral(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        if chain.id != Network.Mainnet: return
        proxy_registry = contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
        cdp_manager = contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
        vat = contract('0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B')
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        ilk = encode_single('bytes32', b'YFI-A')
        collateral = {}
        for address in self.addresses:
            proxy = proxy_registry.proxies(address)
            cdp = cdp_manager.first(proxy)
            urn = cdp_manager.urns(cdp)
            ink = vat.urns(ilk, urn, block_identifier=block).dict()["ink"]
            if ink:
                collateral[address] = {
                    yfi: {
                        'balance': ink / 10 ** 18,
                        'usd value': ink / 10 ** 18 * get_price(yfi, block) if ink > 0 else 0,
                    }
                }
        return collateral

    def unit_collateral(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        if chain.id != Network.Mainnet: return
        if block and block < 11315910: return
        
        # NOTE: This only works for YFI collateral, must extend before using for other collaterals
        unitVault = contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        collateral = {}
        for address in self.addresses:
            bal = unitVault.collaterals(yfi, address, block_identifier=block)
            if bal:
                collateral[address] = {
                    yfi: {
                        'balance': bal / 10 ** 18,
                        'usd value': bal / 10 ** 18 * get_price(yfi, block),
                    }
                }
        return collateral

    # descriptive functions
    # debt

    def debt(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        debt = {address: {} for address in self.addresses}

        maker_debt = self.maker_debt(block=block)
        if maker_debt:
            for address, data in maker_debt.items():
                debt[address].update(data)
        
        unit_debt = self.unit_debt(block=block)
        if unit_debt:
            for address, data in unit_debt.items():
                debt[address].update(data)

        compound_debt = self.compound_debt(block=block)
        if compound_debt:
            for address, data in compound_debt.items():
                debt[address].update(data)

        debt = {key: value for key, value in debt.items() if len(value)}
        return debt

    def maker_debt(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        if chain.id != Network.Mainnet: return
        proxy_registry = contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
        cdp_manager = contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
        vat = contract('0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B')
        ilk = encode_single('bytes32', b'YFI-A')
        dai = '0x6B175474E89094C44Da98b954EedeAC495271d0F'
        maker_debt = {}
        ilk = encode_single('bytes32', b'YFI-A')
        for address in self.addresses:
            proxy = proxy_registry.proxies(address)
            cdp = cdp_manager.first(proxy)
            urn = cdp_manager.urns(cdp)
            art = vat.urns(ilk, urn, block_identifier=block).dict()["art"]
            rate = vat.ilks(ilk, block_identifier=block).dict()["rate"]
            debt = art * rate / 1e45
            maker_debt[address] = {dai: {'balance': debt, 'usd value': debt}}
        return maker_debt

    def unit_debt(self, block: Optional[Block] = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        if chain.id != Network.Mainnet:
            return
        if block and block < 11315910:
            return
        # NOTE: This only works for YFI based debt, must extend before using for other collaterals
        unitVault = contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        usdp = '0x1456688345527bE1f37E9e627DA0837D6f08C925'
        unit_debt = {}
        for address in self.addresses:
            debt = unitVault.getTotalDebt(yfi, address, block_identifier=block) / 10 ** 18
            unit_debt[address] = {usdp: {'balance': debt, 'usd value': debt}}
        return unit_debt
        
    def compound_debt(self, block: Optional[Block] = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        if not compound.compound: # if yearn.prices.compound doesn't support any Compound forks on current chain
            return None

        markets = {market.ctoken for comp in compound.compound.compounds for market in comp.markets}
        gas_token_markets = [market for market in markets if not hasattr(market,'underlying')]
        other_markets = [market for market in markets if hasattr(market,'underlying')]
        markets = gas_token_markets + other_markets
        underlyings = [weth for market in gas_token_markets] + fetch_multicall(*[[market,'underlying'] for market in other_markets])
        
        markets_zip = zip(markets,underlyings)
        markets, underlyings = [], []
        for ctoken, underlying in markets_zip:
            if underlying != ZERO_ADDRESS:
                markets.append(ctoken)
                underlyings.append(underlying)
        
        underlying_contracts = [contract(underlying) for underlying in underlyings]
        underlying_decimals = fetch_multicall(*[[underlying,'decimals'] for underlying in underlying_contracts])

        compound_debt = {}
        for address in self.addresses:
            debts = fetch_multicall(*[[market,'borrowBalanceStored',address] for market in markets],block=block)
            debts = [debt / 10 ** decimals if debt else None for debt, decimals in zip(debts,underlying_decimals)]
            compound_debt[address] = {str(underlying): {'balance': debt, 'usd value': debt * get_price(underlying, block=block)} for underlying, debt in zip(underlyings,debts) if debt}
        return compound_debt

    def aave_debt(self, block: int = None) -> Dict[EthAddress,Dict[EthAddress,Dict[str,float]]]:
        # TODO: don't need this yet but I want to add anyway for completeness
        pass

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


    def process_transfers(self, logs: List) -> None:
        for log in logs:
            if log.address in NFTS or log.address in SKIP_LOGS:
                continue
            try:
                event = decode_logs(
                    [log]
                )  # NOTE: We have to decode logs here because NFTs prevent us from batch decoding logs
                self._transfers.append(event)
            except:
                logger.error('unable to decode logs, figure out why')
                logger.error(log)

    # export functions

    def describe(self, block: int) -> dict:
        return {'assets': self.assets(block), 'debt': self.debt(block)}

    def export(self, block: int, ts: int) -> None:
        start = time.time()
        data = self.describe(block)
        output_treasury.export(ts, data, self.label)
        logger.info('exported block=%d took=%.3fs', block, time.time() - start)


class YearnTreasury(Treasury):
    def __init__(self, watch_events_forever: bool = False) -> None:
        start_block = {
            Network.Mainnet: 10_502_337,
            Network.Fantom: 18_950_072,
            Network.Gnosis: 20_000_000,
            Network.Arbitrum: 4_837_859,
            Network.Optimism: 18_100_336,
        }[chain.id]
        super().__init__('treasury',TREASURY_WALLETS,watch_events_forever=watch_events_forever,start_block=start_block)

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

class StrategistMultisig(Treasury):
    def __init__(self, watch_events_forever: bool = False) -> None:
        start_block = {
            Network.Mainnet: 11_507_716,
            Network.Fantom: 10_836_306,
            Network.Gnosis: 20_455_212,
            Network.Arbitrum: 2_434_174,
            Network.Optimism: 18_084_577,
        }[chain.id]
        super().__init__('sms',STRATEGIST_MULTISIG,watch_events_forever=watch_events_forever,start_block=start_block)

@lru_cache(maxsize=1)
def _treasury():
    return YearnTreasury(watch_events_forever=True)

@lru_cache(maxsize=1)
def _sms():
    return StrategistMultisig(watch_events_forever=True)
