from lib2to3.pgen2 import token
import asyncio
import logging
import os
import time
import warnings
import telebot
from datetime import datetime, timezone
from functools import lru_cache
from typing import List, Union, Tuple, Callable

import a_sync
import dank_mids
import pandas as pd
from async_lru import alru_cache
from brownie import chain, web3, ZERO_ADDRESS, interface
from brownie.network.event import _EventItem
from discordwebhook import Discord
from sqlalchemy import desc, asc
from web3._utils.events import construct_event_topic_set
from y import Contract, ERC20, Network, get_block_timestamp_async, get_price
from y.utils.events import ProcessedEvents

from yearn.cache import memory
from yearn.db.models import Reports, Event, Transactions, Session, engine, select
from yearn.prices import constants

warnings.filterwarnings("ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*")
warnings.filterwarnings("ignore", ".*Locally compiled and on-chain*")
warnings.filterwarnings("ignore", ".*It has been discarded*")
warnings.filterwarnings("ignore", ".*MismatchedABI*")

# mainnet_public_channel = os.environ.get('TELEGRAM_CHANNEL_1_PUBLIC')
# ftm_public_channel = os.environ.get('TELEGRAM_CHANNEL_250_PUBLIC')
# discord_mainnet = os.environ.get('DISCORD_CHANNEL_1')
# discord_ftm = os.environ.get('DISCORD_CHANNEL_250')

logger = logging.getLogger(__name__)
sync_threads = a_sync.PruningThreadPoolExecutor(8)

VAULT_EXCEPTIONS = [
    '0xcd68c3fC3e94C5AcC10366556b836855D96bfa93', # yvCurve-dETH-f 
]

inv_telegram_key = os.environ.get('WAVEY_ALERTS_BOT_KEY')
ETHERSCANKEY = os.environ.get('ETHERSCAN_KEY')
invbot = telebot.TeleBot(inv_telegram_key)
env = os.environ.get('ENVIRONMENT')
alerts_enabled = True if env == "PROD" else False #or env == "TEST" else False

test_channel = os.environ.get('TELEGRAM_CHANNEL_TEST')
if env == "TEST":
    telegram_key = os.environ.get('WAVEY_ALERTS_BOT_KEY')
    dev_channel = test_channel
    bot = telebot.TeleBot(telegram_key)
else:
    telegram_key = os.environ.get('HARVEST_TRACKER_BOT_KEY')
    bot = telebot.TeleBot(telegram_key)
    dev_channel = os.environ.get('TELEGRAM_CHANNEL_DEV')

OLD_REGISTRY_ENDORSEMENT_BLOCKS = {
    "0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1": 11999957,
    "0xdCD90C7f6324cfa40d7169ef80b12031770B4325": 11720423,
    "0x986b4AFF588a109c09B50A03f42E4110E29D353F": 11881934,
    "0xcB550A6D4C8e3517A939BC79d0c7093eb7cF56B5": 11770630,
    "0xa9fE4601811213c340e850ea305481afF02f5b28": 11927501,
    "0xB8C3B7A2A618C552C23B1E4701109a9E756Bab67": 12019352,
    "0xBFa4D8AA6d8a379aBFe7793399D3DdaCC5bBECBB": 11579535,
    "0x19D3364A399d251E894aC732651be8B0E4e85001": 11682465,
    "0xe11ba472F74869176652C35D30dB89854b5ae84D": 11631914,
    "0xe2F6b9773BF3A015E2aA70741Bde1498bdB9425b": 11579535,
    "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9": 11682465,
    "0x27b7b1ad7288079A66d12350c828D3C00A6F07d7": 12089661,
}

INVERSE_PRIVATE_VAULTS = [
    "0xD4108Bb1185A5c30eA3f4264Fd7783473018Ce17",
    "0x67B9F46BCbA2DF84ECd41cC6511ca33507c9f4E9",
    "0xd395DEC4F1733ff09b750D869eEfa7E0D37C3eE6",
]

REKT = [
    # these vaults are rekt, we will force price to 0
    '0xC4C319E2D4d66CcA4464C0c2B32c9Bd23ebe784e', # rekt alETH
    '0x9848482da3Ee3076165ce6497eDA906E66bB85C5', # rekt jPegd pETH
    '0xEd4064f376cB8d68F770FB1Ff088a3d0F3FF5c4d', # rekt crvETH
]

CHAIN_VALUES = {
    Network.Mainnet: {
        "NETWORK_NAME": "Ethereum Mainnet",
        "NETWORK_SYMBOL": "ETH",
        "EMOJI": "🇪🇹",
        "START_DATE": datetime(2020, 2, 12, tzinfo=timezone.utc),
        "START_BLOCK": 11563389,
        "REGISTRY_ADDRESSES": ["0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804","0xaF1f5e1c19cB68B30aAD73846eFfDf78a5863319"],
        "REGISTRY_DEPLOY_BLOCK": 12045555,
        "REGISTRY_HELPER_ADDRESS": "0xec85C894be162268c834b784CC232398E3E89A12",
        "LENS_ADDRESS": "0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a",
        "LENS_DEPLOY_BLOCK": 12707450,
        "VAULT_ADDRESS030": "0x19D3364A399d251E894aC732651be8B0E4e85001",
        "VAULT_ADDRESS031": "0xdA816459F1AB5631232FE5e97a05BBBb94970c95",
        "KEEPER_CALL_CONTRACT": "0x0a61c2146A7800bdC278833F21EBf56Cd660EE2a",
        "KEEPER_TOKEN": "0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44",
        "KEEPER_WRAPPER": "0x0D26E894C2371AB6D20d99A65E991775e3b5CAd7",
        "YEARN_TREASURY": "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde",
        "STRATEGIST_MULTISIG": "0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7",
        "GOVERNANCE_MULTISIG": "0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52",
        "EXPLORER_URL": "https://etherscan.io/",
        "TENDERLY_CHAIN_IDENTIFIER": "mainnet",
        "TELEGRAM_CHAT_ID": os.environ.get('TELEGRAM_CHANNEL_1_PUBLIC') if env == "PROD" else test_channel,
        "TELEGRAM_CHAT_ID_INVERSE_ALERTS": os.environ.get('TELEGRAM_CHAT_ID_INVERSE_ALERTS') if env == "PROD" else test_channel,
        "DISCORD_CHAN": os.environ.get('DISCORD_CHANNEL_1'),
    },
    Network.Fantom: {
        "NETWORK_NAME": "Fantom",
        "NETWORK_SYMBOL": "FTM",
        "EMOJI": "👻",
        "START_DATE": datetime(2021, 4, 30, tzinfo=timezone.utc),
        "START_BLOCK": 18450847,
        "REGISTRY_ADDRESSES": ["0x727fe1759430df13655ddb0731dE0D0FDE929b04"],
        "REGISTRY_DEPLOY_BLOCK": 18455565,
        "REGISTRY_HELPER_ADDRESS": "0x8CC45f739104b3Bdb98BFfFaF2423cC0f817ccc1",
        "REGISTRY_HELPER_DEPLOY_BLOCK": 18456459,
        "LENS_ADDRESS": "0x97D0bE2a72fc4Db90eD9Dbc2Ea7F03B4968f6938",
        "LENS_DEPLOY_BLOCK": 18842673,
        "VAULT_ADDRESS030": "0x637eC617c86D24E421328e6CAEa1d92114892439",
        "VAULT_ADDRESS031": "0x637eC617c86D24E421328e6CAEa1d92114892439",
        "KEEPER_CALL_CONTRACT": "0x57419fb50fa588fc165acc26449b2bf4c7731458",
        "KEEPER_WRAPPER": "0x0D26E894C2371AB6D20d99A65E991775e3b5CAd7",
        "YEARN_TREASURY": "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a",
        "STRATEGIST_MULTISIG": "0x72a34AbafAB09b15E7191822A679f28E067C4a16",
        "GOVERNANCE_MULTISIG": "0xC0E2830724C946a6748dDFE09753613cd38f6767",
        "EXPLORER_URL": "https://ftmscan.com/",
        "TENDERLY_CHAIN_IDENTIFIER": "fantom",
        "TELEGRAM_CHAT_ID": os.environ.get('TELEGRAM_CHANNEL_250_PUBLIC'),
        "TELEGRAM_CHAT_ID_INVERSE_ALERTS": os.environ.get('TELEGRAM_CHAT_ID_INVERSE_ALERTS'),
        "DISCORD_CHAN": os.environ.get('DISCORD_CHANNEL_250'),
    },
    Network.Arbitrum: {
        "NETWORK_NAME": "Arbitrum",
        "NETWORK_SYMBOL": "ARRB",
        "EMOJI": "🤠",
        "START_DATE": datetime(2021, 9, 14, tzinfo=timezone.utc),
        "START_BLOCK": 4841854,
        "REGISTRY_ADDRESSES": ["0x3199437193625DCcD6F9C9e98BDf93582200Eb1f"],
        "REGISTRY_DEPLOY_BLOCK": 12045555,
        "REGISTRY_HELPER_ADDRESS": "0x237C3623bed7D115Fc77fEB08Dd27E16982d972B",
        "LENS_ADDRESS": "0xcAd10033C86B0C1ED6bfcCAa2FF6779938558E9f",
        "VAULT_ADDRESS030": "0x239e14A19DFF93a17339DCC444f74406C17f8E67",
        "VAULT_ADDRESS031": "0x239e14A19DFF93a17339DCC444f74406C17f8E67",
        "KEEPER_WRAPPER": "0x0D26E894C2371AB6D20d99A65E991775e3b5CAd7",
        "YEARN_TREASURY": "0x1DEb47dCC9a35AD454Bf7f0fCDb03c09792C08c1",
        "STRATEGIST_MULTISIG": "0x6346282DB8323A54E840c6C772B4399C9c655C0d",
        "GOVERNANCE_MULTISIG": "0xb6bc033D34733329971B938fEf32faD7e98E56aD",
        "EXPLORER_URL": "https://arbiscan.io/",
        "TENDERLY_CHAIN_IDENTIFIER": "arbitrum",
        "TELEGRAM_CHAT_ID": os.environ.get('TELEGRAM_CHANNEL_42161_PUBLIC'),
        "DISCORD_CHAN": os.environ.get('DISCORD_CHANNEL_42161'),
    },
    Network.Optimism: {
        "NETWORK_NAME": "Optimism",
        "NETWORK_SYMBOL": "OPT",
        "EMOJI": "🔴",
        "START_DATE": datetime(2022, 8, 6, tzinfo=timezone.utc),
        "START_BLOCK": 24097341,
        "REGISTRY_ADDRESSES": ["0x1ba4eB0F44AB82541E56669e18972b0d6037dfE0", "0x79286Dd38C9017E5423073bAc11F53357Fc5C128"],
        "REGISTRY_DEPLOY_BLOCK": 18097341,
        "REGISTRY_HELPER_ADDRESS": "0x2222aaf54Fe3B10937E91A0C2B8a92c18A636D05",
        "LENS_ADDRESS": "0xD3A93C794ee2798D8f7906493Cd3c2A835aa0074",
        "VAULT_ADDRESS030": "0x0fBeA11f39be912096cEc5cE22F46908B5375c19",
        "VAULT_ADDRESS031": "0x0fBeA11f39be912096cEc5cE22F46908B5375c19",
        "KEEPER_WRAPPER": "0x0D26E894C2371AB6D20d99A65E991775e3b5CAd7",
        "YEARN_TREASURY": "0x84654e35E504452769757AAe5a8C7C6599cBf954",
        "STRATEGIST_MULTISIG": "0xea3a15df68fCdBE44Fdb0DB675B2b3A14a148b26",
        "GOVERNANCE_MULTISIG": "0xF5d9D6133b698cE29567a90Ab35CfB874204B3A7",
        "EXPLORER_URL": "https://optimistic.etherscan.io/",
        "TENDERLY_CHAIN_IDENTIFIER": "optimistic",
        "TELEGRAM_CHAT_ID": os.environ.get('TELEGRAM_CHANNEL_10_PUBLIC'),
        "DISCORD_CHAN": os.environ.get('DISCORD_CHANNEL_10'),
    }
}

TREASURY = CHAIN_VALUES[chain.id]["YEARN_TREASURY"]

if chain.id == 1:
    CRV = '0xD533a949740bb3306d119CC777fa900bA034cd52'
    CRV_CONTRACT = Contract(CRV)
    CRV_ABI = CRV_CONTRACT.abi
    VOTER = '0xF147b8125d2ef93FB6965Db97D6746952a133934'
    YVECRV = '0xc5bDdf9843308380375a611c18B50Fb9341f502A'

KP3R_TOKEN = CHAIN_VALUES[chain.id].get("KEEPER_TOKEN", "")
KEEPER_CALL_CONTRACT = CHAIN_VALUES[chain.id].get("KEEPER_CALL_CONTRACT", "")


# Primary vault interface
vault = Contract(CHAIN_VALUES[chain.id]["VAULT_ADDRESS031"])
vault = web3.eth.contract(str(vault), abi=vault.abi)
topics = construct_event_topic_set(
    vault.events.StrategyReported().abi, web3.codec, {}
)
# Deprecated vault interface
if chain.id == 1:
    vault_v030 = Contract(CHAIN_VALUES[chain.id]["VAULT_ADDRESS030"])
    vault_v030 = web3.eth.contract(CHAIN_VALUES[chain.id]["VAULT_ADDRESS030"], abi=vault_v030.abi)
    topics_v030 = construct_event_topic_set(
        vault_v030.events.StrategyReported().abi, web3.codec, {}
    )

events_to_process: List[Event] = []
transaction_hashes: List[str] = []

def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('a_sync.utils.iterators').disabled = True
    asyncio.get_event_loop().run_until_complete(_main())
	
async def _main(dynamically_find_multi_harvest=False):
    print(f"dynamic multi_harvest detection is enabled: {dynamically_find_multi_harvest}")

    last_reported_block, last_reported_block030 = last_harvest_block()
    # last_reported_block = 16482431
    # last_reported_block030 = 16482431
    print("latest block (v0.3.1+ API)",last_reported_block)
    print("blocks behind (v0.3.1+ API)", chain.height - last_reported_block)
    if chain.id == 1:
        print("latest block (v0.3.0 API)",last_reported_block030)
        print("blocks behind (v0.3.0 API)", chain.height - last_reported_block030)

    filters = [StrategyReportedEvents(last_reported_block+1, dynamically_find_multi_harvest)]
    if chain.id == 1:
        # No old vaults deployed anywhere other than mainnet
        filters.append(StrategyReportedEventsV030(last_reported_block030+1, dynamically_find_multi_harvest))
    
    # while True: # Keep this as a long-running script # <--- disabled this since ypm issues
    tasks: List[asyncio.Task] = []
    async for strategy_report_event in a_sync.as_yielded(*filters):
        new_task = asyncio.create_task(handle_event(strategy_report_event.event, strategy_report_event.multi_harvest))
        tasks.append(new_task)
        clear_finished_tasks(tasks)


async def handle_event(event, multi_harvest):
    endorsed_vaults = await get_vaults()
    txn_hash = event.transaction_hash #.hex()
    if event.address in VAULT_EXCEPTIONS:
        return
    if event.address not in endorsed_vaults:
        # check if a vault from inverse partnership
        if event.address not in INVERSE_PRIVATE_VAULTS:
            print(f"skipping: not endorsed. txn hash {txn_hash}. chain id {chain.id} sync {event.block_number} / {chain.height}.")
            return
    if event.address not in INVERSE_PRIVATE_VAULTS:
        if await get_vault_endorsement_block(event.address) > event.block_number:
            print(f"skipping: not endorsed yet. txn hash {txn_hash}. chain id {chain.id} sync {event.block_number} / {chain.height}.")
            return

    print(txn_hash)
    
    r = Reports(
        chain_id = chain.id,
        multi_harvest = multi_harvest,
        block = event.block_number,
        txn_hash = txn_hash,
        vault_address = event.address,
    )
    try:
        await Contract.coroutine(event.address)
    except ValueError:
        return
    
    r.strategy_address, *event_values = list(event.values())

    # we create some tasks early so they can start processing before we need the results
    strategy_task = asyncio.create_task(Contract.coroutine(r.strategy_address))
    receipt_task = asyncio.create_task(get_transaction_receipt(txn_hash))
    t_task = asyncio.create_task(get_db_transaction(txn_hash, r.block))
    time_task = asyncio.create_task(set_time_attrs(r))

    # now we cache this so we don't need to call it for every event with `vault.decimals()`
    r.vault_decimals = await ERC20(event.address, asynchronous=True).decimals 
    r.gain, r.loss, r.debt_paid, r.total_gain, r.total_loss, r.total_debt, r.debt_added, r.debt_ratio = normalize_event_values(event_values, r.vault_decimals)
    
    strategy = await strategy_task
    
    r.want_token, tx_receipt = await asyncio.gather(get_want(strategy), receipt_task)

    (
        r.vault_symbol,
        r.token_symbol, 
        (r.vault_name, r.vault_api),
        (r.strategy_name, r.strategy_api),
        r.strategist,
        r.want_price_at_block, 
        (r.gov_fee_in_want, r.strategist_fee_in_want),
    ) = await asyncio.gather(
        # all of these are cached
        get_symbol(event.address),
        get_symbol(r.want_token),
        get_name_and_version(event.address),
        get_name_and_version(strategy.address),
        get_strategist(strategy),
        # these arent
        get_want_price(r),
        parse_fees(tx_receipt, r.vault_address, r.strategy_address, r.vault_decimals, r.gain, r.vault_api),
    )
    
    r.gain_post_fees = r.gain - r.loss - r.strategist_fee_in_want - r.gov_fee_in_want
    r.want_gain_usd = r.gain * float(r.want_price_at_block)

    # KeepCRV stuff
    if chain.id == 1:
        decoder = await get_transfer_decoder(CRV)
        decoded_events = decoder(tx_receipt)
        r.keep_crv = 0
        for tfr in decoded_events:
            _from, _to, _val = tfr.args.values()
            if tfr.address == CRV and _from == r.strategy_address and (_to == VOTER or _to == TREASURY):
                r.keep_crv = _val / 1e18
                r.crv_price_usd = await get_price(CRV, r.block, sync=False)
                r.keep_crv_value_usd = r.keep_crv * float(r.crv_price_usd)
        
        if r.keep_crv > 0:
            decoder = await get_transfer_decoder(YVECRV)
            decoded_events = decoder(tx_receipt)
            try:
                r.keep_crv_percent = await get_keepcrv(strategy)
            except:
                pass
            for tfr in decoded_events:
                _from, _to, _val = tfr.args.values()
                if tfr.address == YVECRV and _from == ZERO_ADDRESS:
                    r.yvecrv_minted = _val/1e18
    
    await asyncio.gather(time_task)

    r.updated_timestamp = datetime.now()

    with Session(engine) as session:
        # the result should be ready by now, lets grab it
        t = await t_task
        query = select(Reports).where(
            Reports.chain_id == chain.id, Reports.strategy_address == r.strategy_address
        ).order_by(desc(Reports.block))

        previous_report = session.exec(query).first()
        checks = 1
        while previous_report is None:
            print('no previous report found on {checks}th check')
            await asyncio.sleep(60)
            previous_report = session.exec(query).first()
            checks += 1

        r.previous_report_id = previous_report.id
        r.rough_apr_pre_fee, r.rough_apr_post_fee = await compute_apr(r, previous_report)
        
        try:
            # Insert to database
            await db_insert(r)
            print(f"report added. strategy {r.strategy_address} txn hash {r.txn_hash}. chain id {r.chain_id} sync {r.block} / {chain.height}.")
            prepare_alerts(r, t)
        except Exception as e:
            print(f"skipped duplicate record. strategy: {r.strategy_address} at tx hash: {r.txn_hash} {e}")


@alru_cache(maxsize=1)
async def get_vaults() -> List[str]:
    registry_helper = await Contract.coroutine(CHAIN_VALUES[chain.id]["REGISTRY_HELPER_ADDRESS"])
    return list(await registry_helper.getVaults.coroutine())

@alru_cache(maxsize=None)
async def get_keepcrv(strategy: Contract) -> int:
    return await strategy.keepCRV.coroutine()

@alru_cache(maxsize=None)
async def get_strategist(strategy: Contract) -> str:
    return await strategy.strategist.coroutine()

@alru_cache(maxsize=None)
async def get_want(strategy: Contract) -> str:
    want = await strategy.want.coroutine()
    print(f'Want token = {want}')
    return want

@alru_cache(maxsize=None)
async def get_block(number: int) -> dict:
    return await dank_mids.eth.get_block(number)

@alru_cache(maxsize=None)
async def get_transaction(hash: str) -> dict:
    return await dank_mids.eth.get_transaction(hash)

@alru_cache(maxsize=None, ttl=60*60)
async def get_transaction_receipt(hash: str) -> dict:
    return await dank_mids.eth.get_transaction_receipt(hash)

@lru_cache(maxsize=None)
def get_date_string(timestamp: int) -> str:
    return datetime.utcfromtimestamp(timestamp).strftime("%m/%d/%Y, %H:%M:%S")

@alru_cache(maxsize=None)
async def get_name_and_version(address: str) -> Tuple[str, str]:
    contract = await Contract.coroutine(address)
    return await asyncio.gather(ERC20(address, asynchronous=True).name, contract.apiVersion.coroutine())

@alru_cache(maxsize=None)
async def get_symbol(token: str) -> str:
    return await ERC20(token, asynchronous=True).symbol


@alru_cache(maxsize=None, ttl=60*30)
async def get_db_transaction(txhash: str, block: int) -> Transactions:
    if t := await sync_threads.run(transaction_record_exists, txhash):
        return t
    t = Transactions(chain_id=chain.id, txn_hash=txhash, block=block)
    await asyncio.gather(*[setter(t) for setter in _t_attr_setters])
    t.updated_timestamp = datetime.now()
    await db_insert(t)
    return t

async def set_time_attrs(o: Union[Transactions, Reports]) -> None:
    o.timestamp = await get_block_timestamp_async(o.block)
    o.date = datetime.utcfromtimestamp(o.timestamp)
    o.date_string = get_date_string(o.timestamp)

async def set_gas_attrs(t: Transactions) -> None:
    price_task = asyncio.create_task(get_price(constants.weth, t.block, sync=False))
    tx = await get_transaction(t.txn_hash)
    gas_price = tx.gasPrice
    t.txn_gas_price = gas_price / 10 ** 9 # Use gwei
    receipt = await get_transaction_receipt(t.txn_hash)
    t.call_cost_eth = gas_price * receipt.gasUsed / 10 ** 18
    t.eth_price_at_block = await price_task
    t.call_cost_usd = float(t.eth_price_at_block) * float(t.call_cost_eth)

async def set_receipt_attrs(t: Transactions) -> None:
    if chain.id == 1:
        kp3r_price_task = asyncio.create_task(
            get_price(KP3R_TOKEN, t.block, sync=False)
        )

    receipt = await get_transaction_receipt(t.txn_hash)
    t.txn_to = receipt.to
    t.txn_from = receipt["from"]
    t.txn_gas_used = receipt.gasUsed

    if chain.id == 1:
        t.kp3r_price_at_block, t.kp3r_paid = await asyncio.gather(kp3r_price_task, get_keeper_payment(receipt))
        t.kp3r_paid /= 10 ** 18
        t.kp3r_paid_usd = float(t.kp3r_paid) * float(t.kp3r_price_at_block)
        t.keeper_called = t.kp3r_paid > 0
    else:
        t.keeper_called = t.txn_to == KEEPER_CALL_CONTRACT

_t_attr_setters = set_time_attrs, set_gas_attrs, set_receipt_attrs


@a_sync.a_sync(default='async')
def db_insert(obj) -> None:
    with Session(engine) as session:
        session.add(obj)
        session.commit()

async def get_want_price(r: Reports):
    if r.vault_address == '0x9E0E0AF468FbD041Cab7883c5eEf16D1A99a47C3':
        return 1
    elif r.want_token in REKT:
        return 0
    return await get_price(r.want_token, r.block, sync=False)

@lru_cache(maxsize=None)
def transaction_record_exists(txn_hash):
    with Session(engine) as session:
        query = select(Transactions).where(
            Transactions.txn_hash == txn_hash
        )
        result = session.exec(query).first()
        if result == None:
            return False
        return result

def last_harvest_block():
    with Session(engine) as session:
        query = select(Reports.block).where(
            Reports.chain_id == chain.id, Reports.vault_api != "0.3.0"
        ).order_by(desc(Reports.block))
        result1 = session.exec(query).first()
        if result1 == None:
            result1 = CHAIN_VALUES[chain.id]["START_BLOCK"]
        if chain.id == 1:
            query = select(Reports.block).where(
                Reports.chain_id == chain.id, Reports.vault_api == "0.3.0"
            ).order_by(desc(Reports.block))
            result2 = session.exec(query).first()
            if result2 == None:
                result2 = CHAIN_VALUES[chain.id]["START_BLOCK"]
        else:
            result2 = 0
            
    return result1, result2

async def get_keeper_payment(receipt):
    amount = 0
    decoder, denominator = await asyncio.gather(get_transfer_decoder(KP3R_TOKEN), ERC20(KP3R_TOKEN, asynchronous=True).scale)
    decoded_events = decoder(receipt)
    for e in decoded_events:
        if e.address == KP3R_TOKEN:
            sender, receiver, token_amount = e.args.values()
            token_amount = token_amount / denominator
            if receiver == receipt["from"]:
                amount = token_amount
    return amount

@alru_cache(maxsize=None)
async def get_transfer_decoder(address: str) -> Callable:
    contract = await Contract.coroutine(address)
    return web3.eth.contract(str(address), abi=contract.abi).events.Transfer().processReceipt

async def compute_apr(report: Reports, previous_report):
    SECONDS_IN_A_YEAR = 31557600
    seconds_between_reports = report.timestamp - previous_report.timestamp
    pre_fee_apr = 0
    post_fee_apr = 0

    if report.vault_address == '0x27B5739e22ad9033bcBf192059122d163b60349D':
        vault, vault_scale = await asyncio.gather(
            Contract.coroutine(report.vault_address),
            ERC20(report.vault_address, asynchronous=True).scale,
        )
        total_assets = await vault.totalAssets.coroutine(block_identifier=report.block)
        if total_assets == 0 or seconds_between_reports == 0:
            return 0, 0
        pre_fee_apr = report.gain / int(total_assets/vault_scale) * (SECONDS_IN_A_YEAR / seconds_between_reports)
        if report.gain_post_fees != 0:
            post_fee_apr = report.gain_post_fees / int(total_assets/vault_scale) * (SECONDS_IN_A_YEAR / seconds_between_reports)
    else:
        if int(previous_report.total_debt) == 0 or seconds_between_reports == 0:
            return 0, 0
        else:
            pre_fee_apr = report.gain / int(previous_report.total_debt) * (SECONDS_IN_A_YEAR / seconds_between_reports)
            if report.gain_post_fees != 0:
                post_fee_apr = report.gain_post_fees / int(previous_report.total_debt) * (SECONDS_IN_A_YEAR / seconds_between_reports)
    return pre_fee_apr, post_fee_apr

async def parse_fees(tx, vault_address, strategy_address, decimals, gain, vault_version):
    v = int(''.join(x for x in vault_version.split('.')))
    if v < 35 and gain == 0:
        return 0, 0
    denominator = 10 ** decimals
    treasury = CHAIN_VALUES[chain.id]["YEARN_TREASURY"]
    vault = await Contract.coroutine(vault_address)
    decoder = await get_transfer_decoder(vault_address)
    transfers = decoder(tx)

    amount = 0
    gov_fee_in_underlying = 0
    strategist_fee_in_underlying = 0
    counter = 0
    """
      Using the counter, we will keep track to ensure the expected sequence of fee Transfer events is followed.
      Fee transfers always follow this sequence: 
      1. mint
      2. transfer to strategy
      3. transfer to treasury
    """
    for e in transfers:
        if e.address == vault_address:
            sender, receiver, token_amount = e.args.values()
            token_amount = token_amount / denominator
            if sender == ZERO_ADDRESS:
                counter = 1
                continue
            if receiver == strategy_address and counter == 1:
                counter = 2
                strategist_fee_in_underlying = (
                    token_amount * (
                        await vault.pricePerShare.coroutine(block_identifier=tx.blockNumber) /
                        denominator
                    )
                )
                continue
            if receiver == treasury and (counter == 1 or counter == 2):
                counter = 0
                gov_fee_in_underlying = (
                    token_amount * (
                        await vault.pricePerShare.coroutine(block_identifier=tx.blockNumber) /
                        denominator
                    )
                )
                continue
            elif counter == 1 or counter == 2:
                counter = 0
    return gov_fee_in_underlying, strategist_fee_in_underlying

@alru_cache(maxsize=None)
async def get_vault_endorsement_block(vault_address) -> int:
    """An async wrapper for `_get_vault_endorsement_block`"""
    return await sync_threads.run(_get_vault_endorsement_block, vault_address)

@memory.cache()
def _get_vault_endorsement_block(vault_address) -> int:
    token = Contract(vault_address).token()
    try:
        block = OLD_REGISTRY_ENDORSEMENT_BLOCKS[vault_address]
        return block
    except KeyError:
        pass
    registries = CHAIN_VALUES[chain.id]["REGISTRY_ADDRESSES"]
    height = chain.height
    v = '0x5B8C556B8b2a78696F0B9B830B3d67623122E270'
    for r in registries:
        r = Contract(r)
        lo, hi = CHAIN_VALUES[chain.id]["START_BLOCK"], height
        while hi - lo > 1:
            mid = lo + (hi - lo) // 2
            try:
                num_vaults = r.numVaults(token, block_identifier=mid)
                if r.vaults(token, num_vaults-1, block_identifier=mid) == vault_address:
                    hi = mid
                else:
                    lo = mid
            except:
                lo = mid
        if hi < height:
            return mid
    return hi

def normalize_event_values(vals, decimals):
    denominator = 10**decimals
    if len(vals) == 7:
        gain, loss, total_gain, total_loss, total_debt, debt_added, debt_ratio = vals
        debt_paid = 0
    if len(vals) == 8:
        gain, loss, debt_paid, total_gain, total_loss, total_debt, debt_added, debt_ratio = vals
    return (
        gain/denominator, 
        loss/denominator, 
        debt_paid/denominator, 
        total_gain/denominator, 
        total_loss/denominator, 
        total_debt/denominator, 
        debt_added/denominator, 
        debt_ratio
    )

def prepare_alerts(r, t):
    if alerts_enabled:
        if r.vault_address not in INVERSE_PRIVATE_VAULTS:
            m = format_public_telegram(r, t)
            
            # Only send to public TG and Discord on > $0 harvests
            if r.gain != 0:
                bot.send_message(CHAIN_VALUES[chain.id]["TELEGRAM_CHAT_ID"], m, parse_mode="markdown", disable_web_page_preview = True)
                discord = Discord(url=CHAIN_VALUES[chain.id]["DISCORD_CHAN"])
                discord.post(
                    embeds=[{
                        "title": "New harvest", 
                        "description": m
                    }],
                )
            
            # Send to dev channel
            m = f'Network: {CHAIN_VALUES[chain.id]["EMOJI"]} {CHAIN_VALUES[chain.id]["NETWORK_SYMBOL"]}\n\n' + m + format_dev_telegram(r, t)
            bot.send_message(dev_channel, m, parse_mode="markdown", disable_web_page_preview = True)
        else:
            m = format_public_telegram_inv(r, t)
            m = m + format_dev_telegram(r, t)
            invbot.send_message(CHAIN_VALUES[chain.id]["TELEGRAM_CHAT_ID_INVERSE_ALERTS"], m, parse_mode="markdown", disable_web_page_preview = True)

def format_public_telegram(r, t):
    explorer = CHAIN_VALUES[chain.id]["EXPLORER_URL"]
    sms = CHAIN_VALUES[chain.id]["STRATEGIST_MULTISIG"]
    gov = CHAIN_VALUES[chain.id]["GOVERNANCE_MULTISIG"]
    keeper_wrapper = CHAIN_VALUES[chain.id]["KEEPER_WRAPPER"]
    from_indicator = ""

    if t.txn_to == sms or t.txn_to == gov:
        from_indicator = "✍ "

    elif t.txn_from == r.strategist and t.txn_to != sms:
        from_indicator = "🧠 "

    elif (
        t.keeper_called or 
        t.txn_from == KEEPER_CALL_CONTRACT or 
        t.txn_to == KEEPER_CALL_CONTRACT or
        t.txn_to == '0xf4F748D45E03a70a9473394B28c3C7b5572DfA82' # ETH public harvest job
    ):
        from_indicator = "🤖 "

    elif t.txn_to == keeper_wrapper: # Permissionlessly executed by anyone
        from_indicator = "🧍‍♂️ "

    message = ""
    message += from_indicator
    message += f' [{r.vault_name}]({explorer}address/{r.vault_address})  --  [{r.strategy_name}]({explorer}address/{r.strategy_address})\n\n'
    message += f'📅 {r.date_string} UTC \n\n'
    net_profit_want = "{:,.2f}".format(r.gain - r.loss)
    net_profit_usd = "{:,.2f}".format(float(r.gain - r.loss) * float(r.want_price_at_block))
    sym = r.token_symbol.replace('_','-')
    message += f'💰 Net profit: {net_profit_want} {sym} (${net_profit_usd})\n\n'
    txn_cost_str = "${:,.2f}".format(t.call_cost_usd)
    message += f'💸 Transaction Cost: {txn_cost_str} \n\n'
    message += f'🔗 [View on Explorer]({explorer}tx/{r.txn_hash})'
    if r.multi_harvest:
        message += "\n\n_part of a single txn with multiple harvests_"
    return message

def format_public_telegram_inv(r, t):
    explorer = CHAIN_VALUES[chain.id]["EXPLORER_URL"]
    sms = CHAIN_VALUES[chain.id]["STRATEGIST_MULTISIG"]
    gov = CHAIN_VALUES[chain.id]["GOVERNANCE_MULTISIG"]
    from_indicator = ""

    message = f'👨‍🌾 New Harvest Detected!\n\n'
    message += f' [{r.vault_name}]({explorer}address/{r.vault_address})  --  [{r.strategy_name}]({explorer}address/{r.strategy_address})\n'
    message += f'{r.date_string} UTC \n'
    net_profit_want = "{:,.2f}".format(r.gain - r.loss)
    net_profit_usd = "{:,.2f}".format(float(r.gain - r.loss) * r.want_price_at_block)
    sym = r.token_symbol.replace('_','-')
    message += f'Net profit: {net_profit_want} {sym} (${net_profit_usd})\n'
    txn_cost_str = "${:,.2f}".format(t.call_cost_usd)
    message += f'Transaction Cost: {txn_cost_str} \n'
    message += f'[View on Explorer]({explorer}tx/{r.txn_hash})'
    if r.multi_harvest:
        message += "\n\n_part of a single txn with multiple harvests_"
    return message

def format_dev_telegram(r, t):
    tenderly_str = CHAIN_VALUES[chain.id]["TENDERLY_CHAIN_IDENTIFIER"]
    message = f' | [Tenderly](https://dashboard.tenderly.co/tx/{tenderly_str}/{r.txn_hash})\n\n'
    df = pd.DataFrame(index=[''])
    last_harvest_ts = Contract(r.vault_address).strategies(r.strategy_address, block_identifier=r.block-1).dict()["lastReport"]
    if last_harvest_ts == 0:
        time_since_last_report = "n/a"
    else:
        seconds_since_report = int(time.time() - last_harvest_ts)
        time_since_last_report = "%dd, %dhr, %dm" % dhms_from_seconds(seconds_since_report)
    df[r.vault_name + " " + r.vault_api] = r.vault_address
    df["Strategy Address"] = r.strategy_address
    df["Last Report"] = time_since_last_report
    df["Gain"] = "{:,.2f}".format(r.gain) + " | " + "${:,.2f}".format(r.gain * r.want_price_at_block)
    df["Loss"] = "{:,.2f}".format(r.loss) + " | " + "${:,.2f}".format(r.loss * r.want_price_at_block)
    if r.vault_address in INVERSE_PRIVATE_VAULTS:
        fees = r.gov_fee_in_want + r.strategist_fee_in_want
        inverse_profit = r.gain - fees
        df["Yearn Treasury Profit"] = "{:,.2f}".format(fees) + " | " + "${:,.2f}".format(fees * r.want_price_at_block)
        df["Inverse Profit"] = "{:,.2f}".format(inverse_profit) + " | " + "${:,.2f}".format(inverse_profit * r.want_price_at_block)

    else:
        df["Treasury Fee"] = "{:,.2f}".format(r.gov_fee_in_want) + " | " + "${:,.2f}".format(r.gov_fee_in_want * r.want_price_at_block)
    if r.strategy_address == "0xd025b85db175EF1b175Af223BD37f330dB277786":
        df["Strategist Fee"] = "{:,.2f}".format(r.strategist_fee_in_want) + " | " + "${:,.2f}".format(r.strategist_fee_in_want * r.want_price_at_block)
    prefee = "n/a"
    postfee = "n/a"
    df["Debt Paid"] = "{:,.2f}".format(r.debt_paid) + " | " + "${:,.2f}".format(r.debt_paid * r.want_price_at_block)
    df["Debt Added"] = "{:,.2f}".format(r.debt_added) + " | " + "${:,.2f}".format(r.debt_added * r.want_price_at_block)
    df["Total Debt"] = "{:,.2f}".format(r.total_debt) + " | " + "${:,.2f}".format(r.total_debt * r.want_price_at_block)
    df["Debt Ratio"] = r.debt_ratio
    if chain.id == 1 and r.keep_crv > 0:
        df["CRV Locked"] = "{:,.2f}".format(r.keep_crv) + " | " + "${:,.2f}".format(r.keep_crv_value_usd)
    
    if r.rough_apr_pre_fee is not None:
        prefee = "{:.2%}".format(r.rough_apr_pre_fee)
    if r.rough_apr_post_fee is not None:
        postfee = "{:.2%}".format(r.rough_apr_post_fee)
    df["Pre-fee APR"] = prefee
    df["Post-fee APR"] = postfee
    message2 = f"```{df.T.to_string()}\n```"
    return message + message2

def dhms_from_seconds(seconds):
	minutes, seconds = divmod(seconds, 60)
	hours, minutes = divmod(minutes, 60)
	days, hours = divmod(hours, 24)
	return (days, hours, minutes)


class StrategyReportedEvents(ProcessedEvents):
    """We subclass ProcessedEvents so our event filter can do some extra stuff with (ie: 'process') the event before yielding it to us"""
    topics: list = topics
    is_v030: bool = False
    def __init__(self, from_block: int, dynamically_find_multi_harvest: bool) -> None:
        super().__init__(topics=self.topics, from_block=from_block)
        self.dynamically_find_multi_harvest = dynamically_find_multi_harvest
    def _process_event(self, strategy_report_event: _EventItem) -> Event:
        e = Event(self.is_v030, strategy_report_event, strategy_report_event.transaction_hash)
        if self.dynamically_find_multi_harvest:
            # The code below is used to populate the "multi_harvest" property #
            if e.txn_hash in transaction_hashes:
                e.multi_harvest = True
                for i in range(len(events_to_process)):
                    if e.txn_hash == events_to_process[i].txn_hash:
                        events_to_process[i].multi_harvest = True
            else:
                transaction_hashes.append(strategy_report_event.transaction_hash.hex())
        events_to_process.append(e)
        return e
        
class StrategyReportedEventsV030(StrategyReportedEvents):
    """Tweak behavior slightly for v0.3.0"""
    topics = topics_v030
    is_v030 = True

def clear_finished_tasks(tasks: List[asyncio.Task]) -> None:
    for t in tasks[:]:
        if t.done():
            if e := t.exception():
                raise e
            tasks.remove(t)
