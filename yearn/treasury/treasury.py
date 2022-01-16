import logging
import threading
import time

from brownie import ZERO_ADDRESS, Contract, chain, web3
from brownie.network.event import EventLookupError
from eth_abi import encode_single
from eth_utils import encode_hex
from joblib import Parallel, delayed
from yearn.constants import (ERC20_TRANSFER_EVENT_HASH,
                             ERC677_TRANSFER_EVENT_HASH, STRATEGIST_MULTISIG,
                             TREASURY_WALLETS)
from yearn.events import decode_logs
from yearn.exceptions import PriceError
from yearn.multicall2 import fetch_multicall
from yearn.outputs.victoria import output_treasury
from yearn.partners.partners import partners
from yearn.partners.snapshot import WildcardWrapper, Wrapper
from yearn.prices import compound
from yearn.prices.constants import weth
from yearn.prices.magic import get_price
from yearn.prices.magic import logger as logger_price_magic
from yearn.utils import contract

logger = logging.getLogger(__name__)
logger_price_magic.setLevel(logging.CRITICAL)


def _get_price(token, block=None):
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
        price = get_price(token, block)
    except AttributeError:
        logger.error(
            f"AttributeError while getting price for {contract(token).symbol()} {token}"
        )
        raise
    except PriceError:
        logger.error(
            f"PriceError while getting price for {contract(token).symbol()} {token}"
        )
        price = 0
    except ValueError:
        logger.error(
            f"ValueError while getting price for {contract(token).symbol()} {token}"
        )
        price = 0
    return price


def get_token_from_event(event):
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
        logger.critical(
            f'One of your cached contracts has an incorrect definition: {event.address}. Please fix this manually'
        )
        raise



def get_token_from_event(event):
    try:
        return event['Transfer'][0].address
    except EventLookupError:
        logger.critical(
            f'One of your cached contracts has an incorrect definition: {event.address}. Please fix this manually'
        )
        raise Exception(
            f'One of your cached contracts has an incorrect definition: {event.address}. Please fix this manually'
        )


class Treasury:
    '''
    Used to export financial reports
    '''

    def __init__(self, label, wallets, watch_events_forever=False, start_block=0):
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
        self._thread = threading.Thread(target=self.watch_transfers, daemon=True)

    # descriptive functions
    # assets

    def assets(self, block=None) -> dict:
        assets = self.held_assets(block=block)
        assets.update(self.collateral(block=block))
        return assets

    def token_list(self, address, block=None) -> list:
        self.load_transfers()
        tokens = set()
        for event in self._transfers:
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


    def held_assets(self, block=None) -> dict:
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
                block=block
            )
            token_balances = [
                balance / 10 ** decimal if decimal else 0
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

    def collateral(self, block=None) -> dict:
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

    def maker_collateral(self, block=None) -> dict:
        proxy_registry = contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
        cdp_manager = contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
        # ychad = contract('ychad.eth')
        ychad = contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
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

    def unit_collateral(self, block=None) -> dict:
        # NOTE: This only works for YFI collateral, must extend before using for other collaterals
        if block and block < 11315910:
            return
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

    def debt(self, block=None) -> dict:
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

    def maker_debt(self, block=None) -> dict:
        proxy_registry = contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
        cdp_manager = contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
        vat = contract('0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B')
        ilk = encode_single('bytes32', b'YFI-A')
        dai = '0x6B175474E89094C44Da98b954EedeAC495271d0F'
        maker_debt = {}
        for address in self.addresses:
            proxy = proxy_registry.proxies(address)
            cdp = cdp_manager.first(proxy)
            urn = cdp_manager.urns(cdp)
            art = vat.urns(ilk, urn, block_identifier=block).dict()["art"]
            rate = vat.ilks(ilk, block_identifier=block).dict()["rate"]
            debt = art * rate / 1e45
            maker_debt[address] = {dai: {'balance': debt, 'usd value': debt}}
        return maker_debt

    def unit_debt(self, block=None) -> dict:
        # NOTE: This only works for YFI based debt, must extend before using for other collaterals
        if block and block < 11315910:
            return
        unitVault = contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        usdp = '0x1456688345527bE1f37E9e627DA0837D6f08C925'
        unit_debt = {}
        for address in self.addresses:
            debt = unitVault.getTotalDebt(yfi, address, block_identifier=block) / 10 ** 18
            unit_debt[address] = {usdp: {'balance': debt, 'usd value': debt}}
        return unit_debt

    def compound_debt(self, block=None) -> dict:
        markets = {market.ctoken for comp in compound.compound.compounds for market in comp.markets}
        gas_token_markets = [market for market in markets if not hasattr(market,'underlying')]
        other_markets = [market for market in markets if hasattr(market,'underlying')]
        markets = gas_token_markets + other_markets
        underlyings = [weth for market in gas_token_markets] + fetch_multicall(*[[market,'underlying'] for market in other_markets])
        
        markets_zip = zip(markets,underlyings)
        markets, underlyings = [], []
        for contract, underlying in markets_zip:
            if underlying != ZERO_ADDRESS:
                markets.append(contract)
                underlyings.append(underlying)
        
        underlying_contracts = [Contract(underlying) for underlying in underlyings]
        underlying_decimals = fetch_multicall(*[[underlying,'decimals'] for underlying in underlying_contracts])

        compound_debt = {}
        for address in self.addresses:
            debts = fetch_multicall(*[[market,'borrowBalanceStored',address] for market in markets],block=block)
            debts = [debt / 10 ** decimals if debt else None for debt, decimals in zip(debts,underlying_decimals)]
            compound_debt[address] = {str(underlying): {'balance': debt, 'usd value': debt * get_price(underlying, block=block)} for underlying, debt in zip(underlyings,debts) if debt}
        return compound_debt

    def aave_debt(self, block=None) -> dict:
        # TODO: don't need this yet but I want to add anyway for completeness
        pass

    # helper functions

    def load_transfers(self):
        if not self._thread._started.is_set():
            self._thread.start()
        self._done.wait()

    def watch_transfers(self):
        start = time.time()
        logger.info(
            'pulling treasury transfer events, please wait patiently this takes a while...'
        )
        transfer_filters = [
            web3.eth.filter({"fromBlock": self._start_block, "topics": topics})
            for topics in self._topics
        ]
        for block in chain.new_blocks(height_buffer=12):
            for transfer_filter in transfer_filters:
                logs = transfer_filter.get_new_entries()
                self.process_transfers(logs)

            if not self._done.is_set():
                self._done.set()
                logger.info(
                    f"loaded {self.label} transfer events in %.3fs", time.time() - start
                )
            if not self._watch_events_forever:
                break
            time.sleep(5)

    def process_transfers(self, logs):
        for log in logs:
            try:
                event = decode_logs(
                    [log]
                )  # NOTE: We have to decode logs here because NFTs prevent us from batch decoding logs
                self._transfers.append(event)
            except:
                if log.address in [
                    # These are NFTs # TODO 
                    '0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85', # ENS domains
                    '0x01234567bac6fF94d7E4f0EE23119CF848F93245', # EthBlocks
                    '0xD7aBCFd05a9ba3ACbc164624402fB2E95eC41be6', # EthJuanchos
                    '0xeF81c2C98cb9718003A89908e6bd1a5fA8A098A3', # SpaceShiba
                    '0xD1E5b0FF1287aA9f9A268759062E4Ab08b9Dacbe', # .crypto Domain
                    '0x437a6B880d4b3Be9ed93BD66D6B7f872fc0f5b5E', # Soda
                    ]:
                    pass
                else:
                    print('unable to decode logs, figure out why')
                    print(log)

    # export functions

    def describe(self, block) -> dict:
        return {'assets': self.assets(block), 'debt': self.debt(block)}

    def export(self, block, ts):
        start = time.time()
        data = self.describe(block)
        output_treasury.export(ts, data, self.label)
        logger.info('exported block=%d took=%.3fs', block, time.time() - start)


class YearnTreasury(Treasury):
    def __init__(self,watch_events_forever=False):
        super().__init__('treasury',TREASURY_WALLETS,watch_events_forever=watch_events_forever,start_block=10502337)

    def partners_debt(self, block=None) -> dict:
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
    def __init__(self,watch_events_forever=False):
        super().__init__('sms',STRATEGIST_MULTISIG,watch_events_forever=watch_events_forever,start_block=11507716)
