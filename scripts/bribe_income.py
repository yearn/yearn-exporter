from collections import defaultdict
from datetime import datetime

from brownie import ZERO_ADDRESS, chain, web3
from rich import print
from rich.progress import track
from rich.table import Table
from web3._utils.events import construct_event_topic_set
from yearn.prices.magic import get_price
from yearn.utils import contract, closest_block_after_timestamp
from brownie.exceptions import ContractNotFound

def closest_block():
    ts = 1649304000
    ts = 1649289600
    print(closest_block_after_timestamp(ts))

def main():
    my_addresses = [
        '0xF147b8125d2ef93FB6965Db97D6746952a133934'
    ]
    
    from_block = 12316532
    dai = contract("0x6B175474E89094C44Da98b954EedeAC495271d0F")
    dai = web3.eth.contract(str(dai), abi=dai.abi)
    print(f"Starting from block {from_block}")

    print(f"abi: {dai.events.Transfer().abi}")
    
    topics = construct_event_topic_set(
        dai.events.Transfer().abi,
        web3.codec,
        {'dst': my_addresses, 'src': "0x7893bbb46613d7a4FbcC31Dab4C9b823FfeE1026"},
    )
    logs = web3.eth.get_logs(
        {'topics': topics, 'fromBlock': from_block, 'toBlock': chain.height}
    )

    events = dai.events.Transfer().processReceipt({'logs': logs})
    income_by_month = defaultdict(float)
    tokens_by_month = defaultdict(str)
    grand_total = 0

    for event in track(events):
        ts = chain[event.blockNumber].timestamp
        token = event.address
        txn_hash = event.transactionHash.hex()
        tx = web3.eth.getTransaction(txn_hash)
        
        token_contract = contract(token)

        src, dst, amount = event.args.values()
        
        if src in my_addresses:
            print("Sent to self")
            continue
        
        try:
            price = get_price(event.address, block=event.blockNumber)
        except:
            print(
                "Pricing error for",
                token_contract.symbol(),
                "on",
                token_contract.address,
                "****************************************",
            )
            print(f"Amount: {amount}")
            continue
        print("\nDate:", datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d'))

        try:
            amount /= 10 ** contract(token).decimals()
        except (ValueError, ContractNotFound, AttributeError):
            continue

        try:
            price = get_price(event.address, block=event.blockNumber)
        except:
            print("\nPricing error for", token_contract.symbol(), "on", token_contract.address, "****************************************")
            print(f"Amount: {amount}")
            continue
        symbol = token_contract.symbol()
        print("\nToken Symbol:", symbol)
        print(f"Amount: {amount}")
        print(f"Price: {price}")
        print(txn_hash)
        month = datetime.utcfromtimestamp(ts).strftime('%Y-%m')
        grand_total += amount * price
        income_by_month[month] += amount * price
        if tokens_by_month[month]:
            if symbol not in tokens_by_month[month]:
                tokens_by_month[month] = tokens_by_month[month] + ", " + symbol
        else:
            tokens_by_month[month] = symbol



    table = Table()
    table.add_column('month')
    table.add_column('value claimed')
    table.add_column('tokens claimed')
    for month in sorted(income_by_month):
        table.add_row(month, f'{"${:,.0f}".format(income_by_month[month])}',f'{tokens_by_month[month]}')
        # table.add_row(month, f'{tokens_by_month[month]}')

    print(table)
    print(sum(income_by_month.values()))
    print("${:,.2f}".format(grand_total))