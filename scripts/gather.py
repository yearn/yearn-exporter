import pandas as pd
import logging
import os
import time
from asyncio import gather, get_event_loop
from datetime import datetime
from brownie import convert
from eth_portfolio import Portfolio, SHITCOINS
from eth_portfolio.typing import PortfolioBalances
from y import Contract, get_block_at_timestamp
from brownie._config import CONFIG

# type hints
start_portfolio: PortfolioBalances
end_portfolio: PortfolioBalances

# settings
repull_data = True
CONFIG.settings["autofetch_sources"] = False
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()))

month = '20240203'
begin_date = datetime(2023, 11, 1, 0, 0)
end_date = datetime(2024, 4, 1, 0, 0)

treasury_wallets = {
    convert.to_address(address) for address in [
        '0x5f0845101857d2A91627478e302357860b1598a1',
        '0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde',
        '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52',
        '0xb99a40fcE04cb740EB79fC04976CA15aF69AaaaE',
        '0xC001d00d425Fa92C4F840baA8f1e0c27c4297a0B',
    ]
}

# shitcoins
SHITCOINS[1].update({
    "0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85",
    "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
    "0x1d41cf24dF81E3134319BC11c308c5589A486166",
    "0xD1E5b0FF1287aA9f9A268759062E4Ab08b9Dacbe",
    "0xE256CF1C7caEff4383DabafEe6Dd53910F97213D",
    "0x1e988ba4692e52Bc50b375bcC8585b95c48AaD77",
    "0xd7C9F0e536dC865Ae858b0C0453Fe76D13c3bEAc",
    "0x7C07F7aBe10CE8e33DC6C5aD68FE033085256A84",
    "0xAa6E8127831c9DE45ae56bB1b0d4D4Da6e5665BD",
    "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F",
    "0x1fc4DB3e7f9124bAAFB7B34346dB7931Dad621C2",
    "0x85D385244D41ac914484FD6fbBaB177c10A86e79",
    "0x053D7DD4dde2B5e4F6146476B95EA8c62cd7c428",
    "0xF3799CBAe9c028c1A590F4463dFF039b8F4986BE",
    "0x3f6740b5898c5D3650ec6eAce9a649Ac791e44D7",
    "0xD7aBCFd05a9ba3ACbc164624402fB2E95eC41be6",
    "0xeaaa790591c646b0436f02f63e8Ca56209FEDE4E",
    "0xeF81c2C98cb9718003A89908e6bd1a5fA8A098A3",
    "0x01234567bac6fF94d7E4f0EE23119CF848F93245",
})

loggers_to_silence = [
    "a_sync.a_sync.abstract",
    "a_sync.a_sync.function",
    "a_sync.a_sync.method",
    "a_sync.a_sync.property",
    "a_sync.primitives.locks.prio_semaphore",
    "a_sync.utils.iterators",
    "eth_portfolio._ydb",
]

for l in loggers_to_silence:
    logging.getLogger(l).setLevel(logging.INFO)

# startup
begin_block = get_block_at_timestamp(begin_date, sync=True)
end_block = get_block_at_timestamp(end_date, sync=True)
print(begin_block)
print(end_block)

data_folder = os.path.join('.','data')
month_data_folder = os.path.join(data_folder, month)
if not os.path.exists(month_data_folder):
   os.makedirs(month_data_folder)


if repull_data:
    start_time = time.time()

    port = Portfolio(treasury_wallets, load_prices=False)

    coros = gather(port.describe(begin_block, sync=False), port.describe(end_block, sync=False))
    start_portfolio, end_portfolio = get_event_loop().run_until_complete(coros)

    # yay, easy!
    start_df = start_portfolio.dataframe
    end_df = end_portfolio.dataframe

    start_df.to_csv(os.path.join('data', month, 'balance_sheet_bom.csv'))
    end_df.to_csv(os.path.join('data', month, 'balance_sheet_eom.csv'))
    print("--- %s seconds ---" % (time.time() - start_time))
else:
    start_df = pd.read_csv(os.path.join('data', month, 'balance_sheet_bom.csv'), index_col = 0)
    end_df =  pd.read_csv(os.path.join('data', month, 'balance_sheet_eom.csv'), index_col = 0)

print(start_df)
print(start_df.columns)

s_summary = start_df.groupby(['category','token'])[['balance','usd_value']].sum().sort_values('usd_value')
e_summary = end_df.groupby(['category','token'])[['balance','usd_value']].sum().sort_values('usd_value')

r_summary = pd.merge(e_summary, s_summary, how='outer', suffixes=('_e', '_s'), left_index = True, right_index=True)

r_summary.fillna(0, inplace=True)

def get_symbol(x):
    try:
        c = Contract(x)
        return c.symbol() if hasattr(c, 'symbol') else x
    except Exception as e:
        print(x)
        print(e)
    return x

r_summary['diff_balance'] = r_summary['balance_e'] - r_summary['balance_s']
r_summary['diff_value_usd'] = r_summary['usd_value_e'] - r_summary['usd_value_s']


r_summary

r_summary.reset_index(inplace=True)
r_summary['symbol'] = r_summary['token'].apply(get_symbol)


r_summary.to_csv(os.path.join(data_folder,month,'balance_sheet.csv'))