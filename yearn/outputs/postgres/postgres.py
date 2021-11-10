import pyodbc
import os
from tables import treasury_table_query, users_table_query, tokens_table_query, addresses_table_query

class PostgresInstance:
    def __init__(self):
        self.connection_string = os.environ('POSTRGES_CONN_STRING')
        self.conn = pyodbc.connect(self.connection_string)
        self.cursor = self.conn.cursor()
        if not self.table_exists('treasury_txs'):
            self.create_table(treasury_table_query)
            print('treasury_txs table created successfully...')
        if not self.table_exists('user_txs'):
            self.create_table(users_table_query)
            print('user_txs table created successfully...')
        if not self.table_exists('tokens'):
            self.create_table(tokens_table_query)
            print('tokens table created successfully...')
        if not self.table_exists('addresses'):
            self.create_table(addresses_table_query)
            print('addresses table created successfully...')

    def table_exists(self, table_name):
        exists = False
        try:
            exists = self.cursor.execute(f"select exists(select relname from pg_class where relname = '{table_name}')").fetchone()[0]
        except:
            raise('we are raising this for testing only, build out handler')
        return exists

    def create_table(self, table_create_query):
        self.cursor.execute(table_create_query)
        self.cursor.commit()

postgres = PostgresInstance()