
from pprint import pprint

from pandas import DataFrame, pivot_table, to_datetime
from pony.orm import db_session, select
from yearn.entities import TreasuryTx, TxGroup
from yearn.treasury.accountant.revenue import REVENUE_LABEL


@db_session
def main():
    # Which txgroups apply?
    txgroups = [t for t in select(t for t in TxGroup) if t.top_txgroup.name == REVENUE_LABEL]

    # Create initial dataframe.
    df = DataFrame([
        {
            'timestamp': timestamp,
            'token': symbol,
            'amount': amount,
            'value_usd': value_usd,
            'chain': chain,
            'txgroup': txgroup,
        }
        for timestamp, symbol, amount, value_usd, chain, txgroup
        in select((tx.timestamp, tx._symbol, tx.amount, tx.value_usd, tx.chain.chain_name, tx.txgroup.name) for tx in TreasuryTx if tx.txgroup in txgroups)
    ])

    # Timestamp must be datetime.
    df.timestamp = to_datetime(df.timestamp, unit='s')

    # Group and sum data.
    grouped = pivot_table(
        df,
        ['amount','value_usd'],
        'timestamp',
        ['token','chain'],
        'sum',
    ).resample('1M').sum().stack(['chain','token'],dropna=True)

    grouped = grouped[grouped.amount > 0]

    pprint(grouped)

    # Group and sum data, again by chain.
    chain_grouped = pivot_table(
        df,
        ['value_usd'],
        'timestamp',
        ['chain', 'txgroup'],
        'sum',
    ).resample('1M').sum().stack().fillna(0)

    chain_grouped = chain_grouped[chain_grouped.value_usd > 0]

    pprint(chain_grouped)
    chain_grouped.to_csv('./reports/revenue.csv')