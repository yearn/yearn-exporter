
from datetime import datetime
from time import time

import pandas as pd
from pony.orm import db_session
from tqdm import tqdm
from yearn.entities import deduplicate_internal_transfers
from yearn.treasury import accountant

pd.set_option('display.max_rows', 1000)
pd.set_option('display.max_colwidth', None)

@db_session
def main():
    deduplicate_internal_transfers()
    txs = accountant.unsorted_txs()
    start_ct, start = len(txs), time()
    accountant.sort_txs(txs)
    print(f"Sorted {start_ct - len(txs)} transactions in {round(time() - start, 2)}s.")
    print(f"{len(txs)} remain:")
    df = pd.DataFrame([
        {  
            'timestamp': datetime.fromtimestamp(tx.timestamp),
            'log index': tx.log_index,
            'from': tx._from_nickname if tx._from_nickname else tx.from_address.address,
            'to': tx._to_nickname if tx._to_nickname else tx.to_address.address if tx.to_address else None,
            'amount': round(tx.amount,6),
            'hash':tx.hash,
            'token': tx.token.symbol,
            'value_usd': round(tx.value_usd,2) if tx.value_usd else None,
        } for tx in tqdm(txs)
    ])

    if len(df) > 0:
        df.sort_values('timestamp',inplace=True)
        print(df)
