import logging
import threading
import time

from brownie import Contract, chain, web3
from brownie.network.event import EventLookupError
from eth_abi import encode_single
from joblib import Parallel, delayed
from yearn.events import create_filter, decode_logs
from yearn.multicall2 import fetch_multicall
from yearn.outputs import victoria
from yearn.partners.partners import partners
from yearn.partners.snapshot import WildcardWrapper, Wrapper
from yearn.prices.constants import weth
from yearn.prices.magic import PriceError, get_price

from ..constants import TREASURY_WALLETS

logger = logging.getLogger(__name__)

def _get_price(token, block=None):
    SKIP_PRICE = ["0xa9517B2E61a57350D6555665292dBC632C76adFe","0xb07de4b2989E180F8907B8C7e617637C26cE2776"]
    try:
        return get_price(token, block)
    except AttributeError:
        if token not in SKIP_PRICE:
            print(f"AttributeError while getting price for {Contract(token).symbol()} {token}")
        return 0
    except PriceError:
        return 0
    except ValueError:
        if token not in SKIP_PRICE:
            print(f"ValueError while getting price for {Contract(token).symbol()} {token}")
        return 0

def get_token_from_event(event):
    try:
        return event['Transfer'][0].address
    except EventLookupError:
        logger.critical(f'One of your cached contracts has an incorrect definition: {event.address}. Please fix this manually')
        raise(f'One of your cached contracts has an incorrect definition: {event.address}. Please fix this manually')
       

class Treasury:
    '''
    Used to export Yearn financial reports
    '''
    def __init__(self, watch_events_forever = False):
        self.addresses = list(TREASURY_WALLETS)
        self._transfers = []
        self._topics_in = [
                '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                None,
                ['0x000000000000000000000000' + address[2:] for address in self.addresses]
        ] # Transfers into Yearn wallets
        self._topics_out = [
                '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                ['0x000000000000000000000000' + address[2:] for address in self.addresses]
        ] # Transfers out of Yearn wallets
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
        if block:
            return list({get_token_from_event(transfer) for transfer in self._transfers if transfer['Transfer'].values()[1] == address and transfer['Transfer'][0].block_number <= block})
        else:
            return list({get_token_from_event(transfer) for transfer in self._transfers if transfer['Transfer'].values()[1] == address})

    def held_assets(self,block=None) -> dict:   
        balances = {}
        for address in self.addresses:
            # get token balances
            tokens = self.token_list(address,block=block)
            token_balances = fetch_multicall(*[[Contract(token),"balanceOf",address] for token in tokens], block=block)
            decimals = fetch_multicall(*[[Contract(token),"decimals"] for token in tokens], block=block)
            token_balances = [balance / 10 ** decimal if decimal else 0 for balance, decimal in zip(token_balances,decimals)]
            token_prices = Parallel(8,'threading')(delayed(_get_price)(token,block) for token in tokens)
            token_balances = [{'balance': balance, 'usd value': balance * price} for balance, price in zip(token_balances, token_prices)]
            balances[address] = dict(zip(tokens,token_balances))

            # then, add eth
            if block:
                balance = web3.eth.get_balance(address, block_identifier = block) / 10 ** 18
            else:
                balance = web3.eth.get_balance(address) / 10 ** 18
            balances[address]['ETH'] = {'balance': balance, 'usd value': balance * get_price(weth, block)}
        return balances

    def collateral(self, block=None) -> dict:
        collateral = {
            'MakerDAO': self.maker_collateral(block=block),
        }
        if block is None or block >= 11315910:
            collateral['Unit.xyz'] = self.unit_collateral(block=block)
        return collateral

    def maker_collateral(self, block=None) -> dict:
        proxy_registry = Contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
        cdp_manager = Contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
        #ychad = Contract('ychad.eth')
        ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
        vat = Contract('0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B')
        proxy = proxy_registry.proxies(ychad)
        cdp = cdp_manager.first(proxy)
        urn = cdp_manager.urns(cdp)
        ilk = encode_single('bytes32', b'YFI-A')
        ink = vat.urns(ilk, urn, block_identifier = block).dict()["ink"]
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        collateral = {
            yfi: {
                'balance': ink / 10 ** 18,
                'usd value': ink / 10 ** 18 * get_price(yfi, block) if ink > 0 else 0
            }
        }
        return collateral

    def unit_collateral(self, block=None) -> dict:
        if block and block < 11315910:
            return
        #ychad = Contract('ychad.eth')
        ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
        unitVault = Contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        bal = unitVault.collaterals(yfi,ychad, block_identifier = block) 
        collateral = {
            yfi: {
                'balance': bal / 10 ** 18,
                'usd value': bal / 10 ** 18 * get_price(yfi, block)
            }
        }
        return collateral

    #def bonded_kp3r(self, block=None) -> dict:

    # descriptive functions
    # debt

    def debt(self, block=None) -> dict:
        debt = {
            'MakerDAO': self.maker_debt(block=block),
        }
        if not block or block >= 11315910:
            debt['Unit.xyz'] = self.unit_debt(block=block)
        #self.accounts_payable()
        return debt

    def accounts_payable(self, block=None) -> dict:
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

        
    def maker_debt(self, block=None) -> dict:
        proxy_registry = Contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
        cdp_manager = Contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
        #ychad = Contract('ychad.eth')
        ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
        vat = Contract('0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B')
        proxy = proxy_registry.proxies(ychad)
        cdp = cdp_manager.first(proxy)
        urn = cdp_manager.urns(cdp)
        ilk = encode_single('bytes32', b'YFI-A')
        art = vat.urns(ilk, urn, block_identifier = block).dict()["art"]
        rate = vat.ilks(ilk, block_identifier = block).dict()["rate"]
        debt = art * rate / 1e27
        dai = '0x6B175474E89094C44Da98b954EedeAC495271d0F'
        debt = {
            dai: {
                'balance': debt / 10 ** 18,
                'usd value': debt / 10 ** 18
            }
        }
        return debt

    def unit_debt(self, block=None) -> dict:
        if block and block < 11315910:
            return
        #ychad = Contract('ychad.eth')
        ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
        unitVault = Contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"
        usdp = '0x1456688345527bE1f37E9e627DA0837D6f08C925'
        debt = unitVault.getTotalDebt(yfi,ychad, block_identifier = block) 
        debt = {
            usdp: {
                'balance': debt / 10 ** 18,
                'usd value': debt / 10 ** 18
            }
        }
        return debt

    # helper functions

    def load_transfers(self):
        if not self._thread._started.is_set():
            self._thread.start()
        self._done.wait()

    def watch_transfers(self):
        start = time.time()
        logger.info('pulling treasury transfer events, please wait patiently this takes a while...')
        self.log_filter_in = create_filter(None, topics=self._topics_in)
        self.log_filter_out = create_filter(None, topics=self._topics_out)
        for block in chain.new_blocks(height_buffer=12):
            logs = self.log_filter_in.get_new_entries()
            self.process_transfers(logs)
            logs = self.log_filter_out.get_new_entries()
            self.process_transfers(logs)
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded treasury transfer events in %.3fs", time.time() - start)
            if not self._watch_events_forever:
                break
            time.sleep(300)

    def process_transfers(self, logs):
        for log in logs:
            try:
                event = decode_logs([log]) # NOTE: We have to decode logs here because silly SHIBAS token prevents us from batch decoding logs
                self._transfers.append(event)
            except:
                if log.address == '0xeF81c2C98cb9718003A89908e6bd1a5fA8A098A3':
                    print('skipping spaceshiba token, logs are formed weird')
                else:
                    print('unable to decode logs, figure out why')
                    print(log)

    

    

    
    # export functions

    def describe(self, block) -> dict:
        return {
            'assets': self.assets(block),
            'debt': self.debt(block)
        }

    def export(self, block, ts):
        start = time.time()
        data = self.describe(block)
        victoria.export_treasury(ts, data)
        logger.info('exported block=%d took=%.3fs', block, time.time() - start)
