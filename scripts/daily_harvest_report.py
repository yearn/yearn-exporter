import time, os
from datetime import datetime
import telebot
from discordwebhook import Discord
from yearn.db.models import Reports, Event, Transactions, Session, engine, select
from sqlalchemy import desc, asc

telegram_key = os.environ.get('HARVEST_TRACKER_BOT_KEY')
mainnet_public_channel = os.environ.get('TELEGRAM_CHANNEL_1_PUBLIC')
ftm_public_channel = os.environ.get('TELEGRAM_CHANNEL_250_PUBLIC')
dev_channel = os.environ.get('TELEGRAM_CHANNEL_DEV')
discord_mainnet = os.environ.get('DISCORD_CHANNEL_1')
discord_ftm = os.environ.get('DISCORD_CHANNEL_250')
discord_daily_report = os.environ.get('DISCORD_CHANNEL_DAILY_REPORT')
discord = Discord(url=discord_daily_report)
bot = telebot.TeleBot(telegram_key)
alerts_enabled = True if os.environ.get('ENVIRONMENT') == "PROD" else False

RESULTS = {
    1: {
        "network_symbol": "ETH",
        "network_name": "Ethereum",
        "telegram_channel": mainnet_public_channel,
        "profit_usd": 0,
        "num_harvests": 0,
        "txn_cost_eth": 0,
        "txn_cost_usd": 0,
        "message": ""
    },
    250: {
        "network_symbol": "FTM",
        "network_name": "Fantom",
        "telegram_channel": ftm_public_channel,
        "profit_usd": 0,
        "num_harvests": 0,
        "txn_cost_eth": 0,
        "txn_cost_usd": 0,
        "message": ""
    },
    42161: {
        "network_symbol": "ARRB",
        "network_name": "Arbitrum",
        "telegram_channel": 0,
        "profit_usd": 0,
        "num_harvests": 0,
        "txn_cost_eth": 0,
        "txn_cost_usd": 0,
        "message": ""
    }
}

def main():
    DAY_IN_SECONDS = 60 * 60 * 24
    current_time = int(time.time())
    yesterday = current_time - DAY_IN_SECONDS
    txn_list = []
    with Session(engine) as session:
        query = select(Reports, Transactions).join(Transactions).where(
            Reports.timestamp > yesterday
        ).order_by(desc(Reports.block))
        results = session.exec(query)
        for report, txn in results: 
            RESULTS[txn.chain_id]["profit_usd"] = RESULTS[txn.chain_id]["profit_usd"] + report.want_gain_usd
            RESULTS[txn.chain_id]["num_harvests"] = RESULTS[txn.chain_id]["num_harvests"] + 1
            if txn.txn_hash not in txn_list:
                txn_list.append(txn.txn_hash)
                RESULTS[txn.chain_id]["txn_cost_eth"] = RESULTS[txn.chain_id]["txn_cost_eth"] + txn.call_cost_eth
                RESULTS[txn.chain_id]["txn_cost_usd"] = RESULTS[txn.chain_id]["txn_cost_usd"] + txn.call_cost_usd
    # Build Messages
    cumulative_message = ""
    for chain in RESULTS.keys():
        print(RESULTS[chain]["network_symbol"])

        message = f'📃 End of Day Report --- {datetime.utcfromtimestamp(current_time - 1000).strftime("%m-%d-%Y")} \n\n'
        message += f'💰 ${"{:,.2f}".format(RESULTS[chain]["profit_usd"])} harvested\n\n'
        message += f'💸 ${"{:,.2f}".format(RESULTS[chain]["txn_cost_usd"])} in transaction fees\n\n'
        message += f'👨‍🌾 {RESULTS[chain]["num_harvests"]} strategies harvested'
        
        cumulative_message += f'--- {RESULTS[chain]["network_name"]} ---'
        cumulative_message += f'\n💰 ${"{:,.2f}".format(RESULTS[chain]["profit_usd"])} harvested'
        cumulative_message += f'\n💸 ${"{:,.2f}".format(RESULTS[chain]["txn_cost_usd"])} in transaction fees'
        cumulative_message += f'\n👨‍🌾 {RESULTS[chain]["num_harvests"]} strategies harvested\n\n'
        RESULTS[chain]["message"] = message
        channel = RESULTS[chain]["telegram_channel"]
        print()
        if channel != 0:
            bot.send_message(channel, message, parse_mode="markdown", disable_web_page_preview = True)
        print(message)
    date_banner = f'📃 End of Day Report --- {datetime.utcfromtimestamp(current_time - 1000).strftime("%m-%d-%Y")} \n\n'
    discord.post(
        embeds=[{
            "title": date_banner, 
            "description": cumulative_message
        }],
    )
    bot.send_message(dev_channel, date_banner + cumulative_message, parse_mode="markdown", disable_web_page_preview = True)