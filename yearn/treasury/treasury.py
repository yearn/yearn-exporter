import logging
import threading
import time
from collections import Counter

from brownie import Contract, chain, multicall, web3
from yearn.events import create_filter, decode_logs
from yearn.outputs import victoria
from ypricemagic.constants import weth, dai
#from yearn.prices.magic import get_price
from eth_abi import encode_single
from ypricemagic.magic import PriceError, get_price
from ypricemagic.utils.utils import Contract_with_erc20_fallback
from yearn.multicall2 import multicall2

from ..constants import TREASURY_WALLETS

logger = logging.getLogger(__name__)



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

    def held_assets(self,block=None) -> dict:
        self.load_transfers()
        if block:
            transfers = [transfer for transfer in self._transfers if transfer['Transfer'][0].block_number <= block]
        else:
            transfers = [transfer for transfer in self._transfers]
        
        balances = {}
        for address in self.addresses:
            if block:
                balance = web3.eth.get_balance(address, block_identifier = block) / 10 ** 18
            else:
                balance = web3.eth.get_balance(address) / 10 ** 18

            balances[address] = {
                'ETH': {
                    'balance': balance,
                    'usd value': balance * get_price(weth, block)
                    }
                }

            token_balances = Counter()
            for transfer in transfers:
                token = transfer['Transfer'][0].address
                sender, receiver, amount = transfer['Transfer'].values()
                if receiver == address:
                    token_balances[token] += amount
                if sender == address:
                    token_balances[token] -= amount
            
            for token, bal in token_balances.items():
                try:
                    decimals = Contract_with_erc20_fallback(token).decimals()
                    balance = bal / 10 ** decimals
                    try:
                        price = get_price(token, block)
                    except PriceError:
                        price = 0
                    balances[address][token] = {
                        'balance': balance,
                        'usd value': balance * price
                    }
                except: # TODO: why is this reverting? 
                    print(f'{token} reverted, investigate why this is reverting')
                
        return balances

    def collateral(self, block=None) -> dict:
        collateral = {
            'MakerDAO': self.maker_collateral(block=block),
        }
        if block >= 11315910:
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
        yfi = "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e"
        collateral = {
            yfi: {
                'balance': ink / 10 ** 18,
                'usd value': ink / 10 ** 18 * get_price(yfi, block)
            }
        }
        return collateral

    def unit_collateral(self, block=None) -> dict:
        if block < 11315910:
            return
        #ychad = Contract('ychad.eth')
        ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
        unitVault = Contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e"
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
        if block >= 11315910:
            debt['Unit.xyz'] = self.unit_debt(block=block)
        return debt

    def accounts_payable(self, block=None) -> dict:
        pass
        
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
        if block < 11315910:
            return
        #ychad = Contract('ychad.eth')
        ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
        unitVault = Contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
        yfi = "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e"
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
