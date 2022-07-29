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
from yearn.events import decode_logs
import warnings
warnings.filterwarnings("ignore", ".*Class SelectOfScalar will not make use of SQL compilation caching.*")
warnings.filterwarnings("ignore", ".*Locally compiled and on-chain*")
warnings.filterwarnings("ignore", ".*It has been discarded*")

def main():
    vault_address = "0xdA816459F1AB5631232FE5e97a05BBBb94970c95"
    txn_hash = "0xba5d72cf3052869c2259470b8f45f2131acd5c00daea0cac6580cd851e9774ea"
    do_work(txn_hash, vault_address)

def do_work(txn_hash, vault_address):
    vault = Contract(vault_address)
    # Set of complex txns to work with
    txn = web3.eth.getTransactionReceipt(txn_hash)
    abi = vault.abi
    contract = web3.eth.contract(vault_address, abi=vault.abi)
    transfers = contract.events["Transfer"]().processReceipt(txn)
    reports = contract.events["StrategyReported"]().processReceipt(txn)
    num_reports_for_vault = 0
    num_fees_in_tx = 0
    for r in reports:
        strategy_address, gain, loss, debt_paid, total_gain, total_loss, total_debt, debt_added, debt_ratio = normalize_event_values(r.args.values(),vault.decimals())
        print(gain)
        if r.address == vault_address and gain > 0:
            num_reports_for_vault = num_reports_for_vault + 1
    for t in transfers:
        if t.address != vault_address:
            continue
        sender, receiver, value = t.args.values()
        if sender == ZERO_ADDRESS and receiver == vault:
            num_fees_in_tx = num_fees_in_tx + 1
    assert False

    # vault_decimals = vault.decimals()
    # treasury_fee_values = []
    # reports_list = [] 
    
    # obj = {
    #     "gain": 0, 
    #     "treasury_fee": treasury_fee_values[counter],
    #     "has_fees": False,
    # }
    # # this line checks if any fees at all were collected
    # for e in transfers:
    #     if e.address != vault_address:
    #         continue
    #     sender, receiver, value = e.args.values()
    #     if sender == ZERO_ADDRESS and receiver == vault:
    #         # Fees collected!
    #         obj["has_fees"] = True

    
    # if obj["has_fees"]:
    #     for e in transfers:
    #         if e.address != vault_address:
    #             continue
    #         sender, receiver, value = e.args.values()
    #         # Here we count number of times we mint vault tokens
    #         # Or should we count sending them from vault to treasury?
    #         if sender == vault_address and receiver == vault.rewards():
    #             treasury_fee_values.append(value)

    # # ZIP
    # counter = 0
    # for r in reports:
    #     if r.address != vault_address:
    #         continue
    #     strategy_address = r.args.get("strategy")
    #     gain = r.args.get("gain")
    #     if gain == 0:
    #         continue
        
    #     counter += 1
    #     reports_list.append(obj)

    # print(strategy_address)
    # print(obj)
    # assert len(reports_list) == len(treasury_fee_values)


    # object = {
    #     "strategy": ZERO_ADDRESS,
    #     "gain": 0,
    #     "fee": 0,
    # }


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