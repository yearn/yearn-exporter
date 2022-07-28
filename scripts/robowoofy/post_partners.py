from yearn.networks import Network
import telebot
import os

chat_id = '-637585930'
token = os.getenv('TELEGRAM_TOKEN')

"""
This script uploads the partners report to the Yearn B2B Telegram channel, where someone will queue up the fee transaction.
"""

def main():
    bot = telebot.TeleBot(token)
    doc = open(f'./research/partners/payouts_{Network.label()}.csv', 'rb')
    bot.send_document(chat_id, doc)
