
from datetime import datetime
from pprint import pprint

import pandas as pd
from pony.orm import db_session
from yearn.treasury import accountant


@db_session
def main():
    txs = accountant.unsorted_txs()
    start_ct = len(txs)
    accountant.sort_txs(txs)

    for tx in txs:
        pprint(accountant.describe_entity(tx))
        
    print(f"Sorted {start_ct - len(txs)} transactions.")
    print(f"{len(txs)} remain.")

    pd.set_option('display.max_rows', 1000)
    pd.set_option('display.max_colwidth', -1)
    df = pd.DataFrame([
        {  
            'timestamp': datetime.fromtimestamp(tx.timestamp),
            'log index': tx.log_index,
            'from': tx.from_address.nickname if tx.from_address.nickname else tx.from_address.address,
            'to': tx.to_address.nickname if tx.to_address and tx.to_address.nickname else tx.to_address.address if tx.to_address else None,
            'amount': round(tx.amount,6),
            'hash':tx.hash,
            'token': tx.token.symbol,
            #'value_usd': round(tx.value_usd,6),
        }
        for tx in txs #if tx.token.symbol == 'BEETS'
    ])
    if len(df) > 0:
        df.sort_values('timestamp',inplace=True)
        print(df)


