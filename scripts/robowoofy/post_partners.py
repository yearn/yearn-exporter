import os

import telebot
from y.networks import Network

chat_id = os.getenv('B2B_TELEGRAM_ID')
token = os.getenv('TELEGRAM_TOKEN')

"""
This script uploads the partners report to the Yearn B2B Telegram channel, where someone will queue up the fee transaction.
"""

def main():
    bot = telebot.TeleBot(token)
    doc = open(f'./research/partners/payouts_{Network.label()}.csv', 'rb')
    bot.send_document(chat_id, doc)
