import os
import pyodbc
from brownie import Contract, chain
from sqlalchemy import create_engine
from yearn.multicall2 import fetch_multicall
from yearn.outputs.postgres.tables import (addresses_table_query,
                                           tokens_table_query,
                                           treasury_table_query,
                                           users_table_query)
from yearn.utils import is_contract

DATABASE = os.environ.get('POSTGRES_DB',os.environ.get('POSTGRES_USER','postgres'))
UID = os.environ.get('POSTGRES_USER','postgres')
PWD = os.environ.get('POSTGRES_PASSWORD','yearn-exporter')

POSTRGES_CONN_STRING = "Driver={PostgreSQL Unicode};Server=postgres;Port:5432;"\
                        f"Database={DATABASE};Uid={UID};Pwd={PWD};"

SQLA_CONN_STRING = f"postgresql://{UID}:{PWD}@postgres/{DATABASE}?port=5432"

class PostgresInstance:
    def __init__(self):
        self.conn = pyodbc.connect(POSTRGES_CONN_STRING)
        self.cursor = self.conn.cursor()
        self.sqla_engine = create_engine(SQLA_CONN_STRING)
        if not self.table_exists('addresses'):
            self.create_table(addresses_table_query)
            print('addresses table created successfully...')
        if not self.table_exists('tokens'):
            self.create_table(tokens_table_query)
            print('tokens table created successfully...')
        if not self.table_exists('treasury_txs'):
            self.create_table(treasury_table_query)
            print('treasury_txs table created successfully...')
        if not self.table_exists('user_txs'):
            self.create_table(users_table_query)
            print('user_txs table created successfully...')
        

    # Table functions

    def table_exists(self, table_name):
        response = self.cursor.execute(f"select exists(select tablename from pg_tables where tablename = '{table_name}')").fetchone()[0]
        return True if response == '1' else False

    def create_table(self, table_create_query):
        self.cursor.execute(table_create_query)
        self.conn.commit()

    def last_recorded_block(self, table_name):
        '''
        This will only work for tables with a `block` column
        '''
        return self.cursor.execute(f'SELECT max(block) from {table_name}').fetchone()[0]

    # Other functions

    def token_exists(self, token_address: str):
        response = self.cursor.execute(f"select exists(select symbol from tokens where token_address = '{token_address}' and chainid = {chain.id})").fetchone()[0]
        return True if response == '1' else False

    def cache_token(self,token_address: str):
        i = 0
        while i < 10:
            try:
                self.cache_address(token_address)
                if not self.token_exists(token_address):
                    token = Contract(token_address)
                    symbol, name, decimals = fetch_multicall([token,'symbol'],[token,'name'],[token,'decimals'])
                    self.cursor.execute(f"INSERT INTO TOKENS (CHAINID, TOKEN_ADDRESS, SYMBOL, NAME, DECIMALS)\
                                            VALUES ({chain.id},'{token_address}','{symbol}','{name}',{decimals})")
                    self.conn.commit()
                    print(f'{symbol} added to postgres')
                return
            except:
                i += 1

    def address_exists(self, address: str):
        response = self.cursor.execute(f"select exists(select address from addresses where address = '{address}' and chainid = {chain.id})").fetchone()[0]
        return True if response == '1' else False

    def cache_address(self,address: str):
        i = 0
        while i < 10:
            try:
                if not self.address_exists(address):
                    self.cursor.execute(f"INSERT INTO ADDRESSES (CHAINID, ADDRESS, IS_CONTRACT)\
                                            VALUES ({chain.id},'{address}',{is_contract(address)})")
                    self.conn.commit()
                return
            except:
                i += 1                

postgres = PostgresInstance()
