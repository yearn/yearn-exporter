import logging
import time, os
import telebot
from discordwebhook import Discord
from dotenv import load_dotenv
from yearn.cache import memory
import pandas as pd
from datetime import datetime, timezone
from brownie import chain, web3, Contract, ZERO_ADDRESS
from web3._utils.events import construct_event_topic_set
from yearn.utils import contract, contract_creation_block
from yearn.prices import magic, constants
from yearn.db.models import Reports, Event, Transactions, Session, engine, select
from sqlalchemy import desc, asc
from yearn.networks import Network
from yearn.events import decode_logs
import warnings
warnings.filterwarnings("ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*")
warnings.filterwarnings("ignore", ".*Locally compiled and on-chain*")
warnings.filterwarnings("ignore", ".*It has been discarded*")

telegram_key = os.environ.get('HARVEST_TRACKER_BOT_KEY')
mainnet_public_channel = os.environ.get('TELEGRAM_CHANNEL_250_PUBLIC')
ftm_public_channel = os.environ.get('TELEGRAM_CHANNEL_250_PUBLIC')
dev_channel = os.environ.get('TELEGRAM_CHANNEL_DEV')
discord_mainnet = os.environ.get('DISCORD_CHANNEL_1')
discord_ftm = os.environ.get('DISCORD_CHANNEL_250')
bot = telebot.TeleBot(telegram_key)
alerts_enabled = True

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


CHAIN_VALUES = {
    Network.Mainnet: {
        "START_DATE": datetime(2020, 2, 12, tzinfo=timezone.utc),
        "START_BLOCK": 11563389,
        "REGISTRY_ADDRESS": "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",
        "REGISTRY_DEPLOY_BLOCK": 12045555,
        "REGISTRY_HELPER_ADDRESS": "0x52CbF68959e082565e7fd4bBb23D9Ccfb8C8C057",
        "LENS_ADDRESS": "0x5b4F3BE554a88Bd0f8d8769B9260be865ba03B4a",
        "LENS_DEPLOY_BLOCK": 12707450,
        "VAULT_ADDRESS030": "0x19D3364A399d251E894aC732651be8B0E4e85001",
        "VAULT_ADDRESS031": "0xdA816459F1AB5631232FE5e97a05BBBb94970c95",
        "KEEPER_CALL_CONTRACT": "0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9",
        "KEEPER_TOKEN": "0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44",
        "YEARN_TREASURY": "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde",
        "STRATEGIST_MULTISIG": "0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7",
        "GOVERNANCE_MULTISIG": "0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52",
        "EXPLORER_URL": "https://etherscan.io/",
    },
    Network.Fantom: {
        "START_DATE": datetime(2021, 4, 30, tzinfo=timezone.utc),
        "START_BLOCK": 18450847,
        "REGISTRY_ADDRESS": "0x727fe1759430df13655ddb0731dE0D0FDE929b04",
        "REGISTRY_DEPLOY_BLOCK": 18455565,
        "REGISTRY_HELPER_ADDRESS": "0x8CC45f739104b3Bdb98BFfFaF2423cC0f817ccc1",
        "REGISTRY_HELPER_DEPLOY_BLOCK": 18456459,
        "LENS_ADDRESS": "0x97D0bE2a72fc4Db90eD9Dbc2Ea7F03B4968f6938",
        "LENS_DEPLOY_BLOCK": 18842673,
        "VAULT_ADDRESS030": "0x637eC617c86D24E421328e6CAEa1d92114892439",
        "VAULT_ADDRESS031": "0x637eC617c86D24E421328e6CAEa1d92114892439",
        "KEEPER_CALL_CONTRACT": "0x39cAcdb557CA1C4a6555E00203B4a00B1c1a94f8",
        "KEEPER_TOKEN": "",
        "YEARN_TREASURY": "0x89716Ad7EDC3be3B35695789C475F3e7A3Deb12a",
        "STRATEGIST_MULTISIG": "0x72a34AbafAB09b15E7191822A679f28E067C4a16",
        "GOVERNANCE_MULTISIG": "0xC0E2830724C946a6748dDFE09753613cd38f6767",
        "EXPLORER_URL": "https://ftmscan.com/",
    },
    Network.Arbitrum: {
        "START_DATE": datetime(2021, 9, 14, tzinfo=timezone.utc),
        "START_BLOCK": 4841854,
        "REGISTRY_ADDRESS": "",
        "REGISTRY_DEPLOY_BLOCK": 12045555,
        "REGISTRY_HELPER_ADDRESS": "",
        "LENS_ADDRESS": "",
        "VAULT_ADDRESS030": "",
        "VAULT_ADDRESS031": "",
        "KEEPER_CALL_CONTRACT": "",
        "KEEPER_TOKEN": "",
        "YEARN_TREASURY": "",
        "STRATEGIST_MULTISIG": "",
        "GOVERNANCE_MULTISIG": "",
    }
}


# Primary vault interface
vault = contract(CHAIN_VALUES[chain.id]["VAULT_ADDRESS031"])
vault = web3.eth.contract(str(vault), abi=vault.abi)
topics = construct_event_topic_set(
    vault.events.StrategyReported().abi, web3.codec, {}
)
# Deprecated vault interface
if chain.id == 1:
    print(CHAIN_VALUES[chain.id]["VAULT_ADDRESS030"])
    vault_v030 = contract(CHAIN_VALUES[chain.id]["VAULT_ADDRESS030"])
    vault_v030 = web3.eth.contract(CHAIN_VALUES[chain.id]["VAULT_ADDRESS030"], abi=vault_v030.abi)
    topics_v030 = construct_event_topic_set(
        vault_v030.events.StrategyReported().abi, web3.codec, {}
    )

def main(dynamically_find_multi_harvest=False):
    print(f"dynamic multi_harvest detection is enabled: {dynamically_find_multi_harvest}")
    interval_seconds = 25

    last_reported_block, last_reported_block030 = last_harvest_block()

    print("latest block (v0.3.1+ API)",last_reported_block)
    print("blocks behind (v0.3.1+ API)", chain.height - last_reported_block)
    if chain.id == 1:
        print("latest block (v0.3.0 API)",last_reported_block030)
        print("blocks behind (v0.3.0 API)", chain.height - last_reported_block030)
    event_filter = web3.eth.filter({'topics': topics, "fromBlock": last_reported_block + 1})
    if chain.id == 1:
        event_filter_v030 = web3.eth.filter({'topics': topics_v030, "fromBlock": last_reported_block030 + 1})
    
    while True: # Keep this as a long-running script
        events_to_process = []
        transaction_hashes = []
        if dynamically_find_multi_harvest:
            # The code below is used to populate the "multi_harvest" property #
            for strategy_report_event in decode_logs(event_filter.get_new_entries()):
                e = Event(False, strategy_report_event, strategy_report_event.transaction_hash.hex())
                if e.txn_hash in transaction_hashes:
                    e.multi_harvest = True
                    for i in range(0, len(events_to_process)):
                            if e.txn_hash == events_to_process[i].txn_hash:
                                events_to_process[i].multi_harvest = True
                else:
                    transaction_hashes.append(strategy_report_event.transaction_hash.hex())
                events_to_process.append(e)
                
            if chain.id == 1: # No old vaults deployed anywhere other than mainnet
                for strategy_report_event in decode_logs(event_filter_v030.get_new_entries()):
                    e = Event(True, strategy_report_event, strategy_report_event.transaction_hash.hex())
                    if e.txn_hash in transaction_hashes:
                        e.multi_harvest = True
                        for i in range(0, len(events_to_process)):
                            if e.txn_hash == events_to_process[i].txn_hash:
                                events_to_process[i].multi_harvest = True
                    else:
                        transaction_hashes.append(strategy_report_event.transaction_hash.hex())
                    events_to_process.append(e)

            for e in events_to_process:
                handle_event(e.event, e.multi_harvest)
            time.sleep(interval_seconds)
        else:
            for strategy_report_event in decode_logs(event_filter.get_new_entries()):
                e = Event(False, strategy_report_event, strategy_report_event.transaction_hash.hex())
                handle_event(e.event, e.multi_harvest)
                
            if chain.id == 1: # Old vault API exists only on Ethereum mainnet
                for strategy_report_event in decode_logs(event_filter_v030.get_new_entries()):
                    e = Event(True, strategy_report_event, strategy_report_event.transaction_hash.hex())
                    handle_event(e.event, e.multi_harvest)

            time.sleep(interval_seconds)

def handle_event(event, multi_harvest):
    endorsed_vaults = list(contract(CHAIN_VALUES[chain.id]["REGISTRY_HELPER_ADDRESS"]).getVaults())
    txn_hash = event.transaction_hash.hex()
    if event.address not in endorsed_vaults:
        print(f"skipping: not endorsed. txn hash {txn_hash}. chain id {chain.id} sync {event.block_number} / {chain.height}.")
        return
    if get_vault_endorsement_block(event.address) > event.block_number:
        print(f"skipping: not endorsed yet. txn hash {txn_hash}. chain id {chain.id} sync {event.block_number} / {chain.height}.")
        return
    
    tx = web3.eth.getTransactionReceipt(txn_hash)
    gas_price = web3.eth.getTransaction(txn_hash).gasPrice
    ts = chain[event.block_number].timestamp
    dt = datetime.utcfromtimestamp(ts).strftime("%m/%d/%Y, %H:%M:%S")
    r = Reports()
    r.multi_harvest = multi_harvest
    r.chain_id = chain.id
    r.vault_address = event.address
    try:
        vault = contract(r.vault_address)
    except ValueError:
        return
    r.vault_decimals = vault.decimals()
    r.strategy_address, r.gain, r.loss, r.debt_paid, r.total_gain, r.total_loss, r.total_debt, r.debt_added, r.debt_ratio = normalize_event_values(event.values(), r.vault_decimals)
    
    txn_record_exists = False
    t = transaction_record_exists(txn_hash)
    if not t:
        t = Transactions()
        t.chain_id = chain.id
        t.txn_hash = txn_hash
        t.block = event.block_number
        t.txn_to = tx.to
        t.txn_from = tx["from"]
        t.txn_gas_used = tx.gasUsed
        t.txn_gas_price = gas_price / 1e9 # Use gwei
        t.eth_price_at_block = magic.get_price(constants.weth, t.block)
        t.call_cost_eth = gas_price * tx.gasUsed / 1e18
        t.call_cost_usd = t.eth_price_at_block * t.call_cost_eth
        if chain.id == 1:
            t.kp3r_price_at_block = magic.get_price(CHAIN_VALUES[chain.id]["KEEPER_TOKEN"], t.block)
            t.kp3r_paid = get_keeper_payment(tx) / 1e18
            t.kp3r_paid_usd = t.kp3r_paid * t.kp3r_price_at_block
            t.keeper_called = t.kp3r_paid > 0
        if chain.id == 250:
            if t.txn_to == CHAIN_VALUES[chain.id]["KEEPER_CALL_CONTRACT"]:
                t.keeper_called = True
            else:
                t.keeper_called = False
        t.date = datetime.utcfromtimestamp(ts)
        t.date_string = dt
        t.timestamp = ts
        t.updated_timestamp = datetime.now()
    else:
        txn_record_exists = True
    r.block = event.block_number
    r.txn_hash = txn_hash
    strategy = contract(r.strategy_address)
    

    r.gov_fee_in_want, r.strategist_fee_in_want = parse_fees(tx, r.vault_address, r.strategy_address, r.vault_decimals)
    r.gain_post_fees = r.gain - r.loss - r.strategist_fee_in_want - r.gov_fee_in_want
    r.token_symbol = contract(strategy.want()).symbol()
    r.want_token = strategy.want()
    r.want_price_at_block = magic.get_price(r.want_token, r.block)
    r.vault_api = vault.apiVersion()
    r.want_gain_usd = r.gain * r.want_price_at_block
    r.vault_name = vault.name()
    r.strategy_name = strategy.name()
    r.strategy_api = strategy.apiVersion()
    r.strategist = strategy.strategist()
    r.vault_symbol = vault.symbol()
    r.date = datetime.utcfromtimestamp(ts)
    r.date_string = dt
    r.timestamp = ts
    r.updated_timestamp = datetime.now()

    with Session(engine) as session:
        query = select(Reports).where(
            Reports.chain_id == chain.id, Reports.strategy_address == r.strategy_address
        ).order_by(desc(Reports.block))
        previous_report = session.exec(query).first()
        if previous_report != None:
            previous_report_id = previous_report.id
            r.previous_report_id = previous_report_id
            r.rough_apr_pre_fee, r.rough_apr_post_fee = compute_apr(r, previous_report)
        # Insert to database
        insert_success = False
        try:
            session.add(r)
            if not txn_record_exists:
                session.add(t)
            session.commit()
            print(f"report added. strategy {r.strategy_address} txn hash {r.txn_hash}. chain id {r.chain_id} sync {r.block} / {chain.height}.")
            insert_success = True
        except:
            print(f"skipped duplicate record. strategy: {r.strategy_address} at tx hash: {r.txn_hash}")
            pass
        if insert_success:
            prepare_alerts(r, t)

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

def get_keeper_payment(tx):
    kp3r_token = CHAIN_VALUES[chain.id]["KEEPER_TOKEN"]
    token = contract(kp3r_token)
    denominator = 10 ** token.decimals()
    token = web3.eth.contract(str(kp3r_token), abi=token.abi)
    decoded_events = token.events.Transfer().processReceipt(tx)
    amount = 0
    for e in decoded_events:
        if e.address == kp3r_token:
            sender, receiver, token_amount = e.args.values()
            token_amount = token_amount / denominator
            if receiver == tx["from"]:
                amount = token_amount
    return amount

def compute_apr(report, previous_report):
    SECONDS_IN_A_YEAR = 31557600
    seconds_between_reports = report.timestamp - previous_report.timestamp
    pre_fee_apr = 0
    post_fee_apr = 0
    if int(previous_report.total_debt) == 0 or seconds_between_reports == 0:
        return 0, 0
    else:
        pre_fee_apr = report.gain / int(previous_report.total_debt) * (SECONDS_IN_A_YEAR / seconds_between_reports)
        if report.gain_post_fees != 0:
            post_fee_apr = report.gain_post_fees / int(previous_report.total_debt) * (SECONDS_IN_A_YEAR / seconds_between_reports)
    return pre_fee_apr, post_fee_apr

def parse_fees(tx, vault_address, strategy_address, decimals):
    denominator = 10 ** decimals
    treasury = CHAIN_VALUES[chain.id]["YEARN_TREASURY"]
    token = contract(vault_address)
    token = web3.eth.contract(str(vault_address), abi=token.abi)
    decoded_events = token.events.Transfer().processReceipt(tx)
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
    for e in decoded_events:
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
                        contract(vault_address).pricePerShare(block_identifier=tx.blockNumber) /
                        denominator
                    )
                )
                continue
            elif counter == 1:
                counter = 0
            if receiver == treasury and counter == 2:
                counter = 0
                gov_fee_in_underlying = (
                    token_amount * (
                        contract(vault_address).pricePerShare(block_identifier=tx.blockNumber) /
                        denominator
                    )
                )
                continue
            elif counter == 1 or counter == 2:
                counter = 0
    return gov_fee_in_underlying, strategist_fee_in_underlying
            
@memory.cache()
def get_vault_endorsement_block(vault_address):
    token = contract(vault_address).token()
    try:
        block = OLD_REGISTRY_ENDORSEMENT_BLOCKS[vault_address]
        return block
    except KeyError:
        pass
    registry = contract(CHAIN_VALUES[chain.id]["REGISTRY_ADDRESS"])
    height = chain.height
    lo, hi = CHAIN_VALUES[chain.id]["START_BLOCK"], height
    while hi - lo > 1:
        mid = lo + (hi - lo) // 2
        try:
            num_vaults = registry.numVaults(token, block_identifier=mid)
            if registry.vaults(token, num_vaults-1, block_identifier=mid) == vault_address:
                hi = mid
            else:
                lo = mid
        except:
            lo = mid
    return hi

def normalize_event_values(vals, decimals):
    denominator = 10**decimals
    if len(vals) == 8:
        strategy_address, gain, loss, total_gain, total_loss, total_debt, debt_added, debt_ratio = vals
        debt_paid = 0
    if len(vals) == 9:
        strategy_address, gain, loss, debt_paid, total_gain, total_loss, total_debt, debt_added, debt_ratio = vals
    return (
        strategy_address, 
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
        m = format_public_telegram(r, t)
        # Send to chain specific channels
        if chain.id == 1:
            bot.send_message(mainnet_public_channel, m, parse_mode="markdown", disable_web_page_preview = True)
            discord = Discord(url=discord_mainnet)
        if chain.id == 250:
            bot.send_message(ftm_public_channel, m, parse_mode="markdown", disable_web_page_preview = True)
            discord = Discord(url=discord_ftm)
        discord.post(
            embeds=[{
                "title": "New harvest", 
                "description": m
            }],
        )
        
        # Send to dev channel
        m = m + format_dev_telegram(r, t)
        bot.send_message(dev_channel, m, parse_mode="markdown", disable_web_page_preview = True)

def format_public_telegram(r, t):
    explorer = CHAIN_VALUES[chain.id]["EXPLORER_URL"]
    sms = CHAIN_VALUES[chain.id]["STRATEGIST_MULTISIG"]
    gov = CHAIN_VALUES[chain.id]["STRATEGIST_MULTISIG"]
    from_indicator = ""

    if t.txn_from == sms or t.txn_from == gov:
        from_indicator = "✍ "

    elif t.txn_from == r.strategist:
        from_indicator = "🧠 "

    elif t.keeper_called:
        from_indicator = "🤖 "

    message = ""
    message += from_indicator
    message += f' [{r.vault_name}]({explorer}address/{r.vault_address})  --  [{r.strategy_name}]({explorer}address/{r.strategy_address})\n\n'
    message += f'📅 {r.date_string} UTC \n\n'
    net_profit_want = "{:,.2f}".format(r.gain - r.loss)
    net_profit_usd = "{:,.2f}".format(r.want_gain_usd)
    message += f'💰 Net profit: {net_profit_want} {r.token_symbol} (${net_profit_usd})\n\n'
    txn_cost_str = "${:,.2f}".format(t.call_cost_usd)
    message += f'💸 Transaction Cost: {txn_cost_str} \n\n'
    message += f'🔗 [View on Explorer]({explorer}tx/{r.txn_hash})'
    if r.multi_harvest:
        message += "\n\n_part of a single txn with multiple harvests_"
    print(message)
    return message

def format_dev_telegram(r, t):
    message = '\n\n'
    df = pd.DataFrame(index=[''])
    df[r.vault_name + " " + r.vault_api] = r.vault_address
    df["Strategy Address"] = r.strategy_address
    df["Gain"] = "{:,.2f}".format(r.gain) + " (" + "${:,.2f}".format(r.gain * r.want_price_at_block) + ")"
    df["Loss"] = "{:,.2f}".format(r.loss) + " (" + "${:,.2f}".format(r.loss * r.want_price_at_block) + ")"
    df["Debt Paid"] = "{:,.2f}".format(r.debt_paid) + " (" + "${:,.2f}".format(r.debt_paid * r.want_price_at_block) + ")"
    df["Debt Added"] = "{:,.2f}".format(r.debt_added) + " (" + "${:,.2f}".format(r.debt_added * r.want_price_at_block) + ")"
    df["Total Debt"] = "{:,.2f}".format(r.total_debt) + " (" + "${:,.2f}".format(r.total_debt * r.want_price_at_block) + ")"
    df["Debt Ratio"] = r.debt_ratio
    df["Treasury Fee"] = "{:,.2f}".format(r.gov_fee_in_want) + " (" + "${:,.2f}".format(r.gov_fee_in_want * r.want_price_at_block) + ")"
    df["Strategist Fee"] = "{:,.2f}".format(r.strategist_fee_in_want) + " (" + "${:,.2f}".format(r.strategist_fee_in_want * r.want_price_at_block) + ")"
    df["Pre-fee APR"] = "{:.2%}".format(r.rough_apr_pre_fee)
    df["Post-fee APR"] = "{:.2%}".format(r.rough_apr_post_fee)
    message2 = f"```{df.T.to_string()}\n```"
    return message + message2


