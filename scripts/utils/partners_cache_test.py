from decimal import Decimal
from time import time
from yearn.partners.partners import partners
from yearn.partners.snapshot import process_partners
from yearn.partners.snapshot import logger, logging

logger.setLevel(logging.DEBUG)

def main():
    start = time()
    clean_df = process_partners(partners, use_postgres_cache=False, verbose=True)
    logger.info('clean df:')
    logger.info(clean_df)
    logger.info(f'took {time() - start}s')

    start = time()
    cached_df = process_partners(partners, use_postgres_cache=False, verbose=True)
    logger.info('cached df:')
    logger.info(cached_df)
    logger.info(f'took {time() - start}s')

    for i in range(len(clean_df)):
        row_len = len(clean_df.iloc[i])
        for x in range(row_len):
            clean_cell = clean_df.iat[i,x]
            cached_cell = cached_df.iat[i,x]
            if type(clean_cell) == Decimal:
                # they don't match perfectly because database can only handle so much decimal precision
                # but if they match to 10 decimals, we can consider them matched
                clean_cell = round(clean_cell, 10)
                cached_cell = round(cached_cell, 10)
            assert type(clean_cell) == type(cached_cell), f"[row,col] = [{i},{x}]  {type(clean_cell)}  {type(cached_cell)}"
            assert clean_cell == cached_cell, f'[row,col] = [{i},{x}]  {clean_cell}  {cached_cell}'
    logger.info('df matches')
