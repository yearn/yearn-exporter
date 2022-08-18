
from pony.orm import db_session
from yearn.treasury import accountant


@db_session
def main():
    txs = accountant.all_txs()
    accountant.sort_txs(txs)
    print(f"Resorted {len(txs)} transactions.")
