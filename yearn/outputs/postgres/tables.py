
treasury_table_query = f"CREATE TABLE TREASURY_TXS(\
                            TIMESTAMP INT NOT NULL,\
                            BLOCK INT NOT NULL,\
                            HASH BYTEA NOT NULL,\
                            FROM BYTEA NOT NULL,\
                            TO BYTEA NOT NULL,\
                            TOKEN BYTEA NOT NULL,\
                            AMOUNT BYTEA NOT NULL,\
                            VALUE_USD MONEY NOT NULL\
                            )"

users_table_query = f"CREATE TABLE USER_TXS(\
                        TIMESTAMP INT NOT NULL,\
                        BLOCK INT NOT NULL,\
                        HASH BYTEA NOT NULL,\
                        FROM BYTEA NOT NULL,\
                        TO BYTEA NOT NULL,\
                        TOKEN BYTEA NOT NULL,\
                        AMOUNT BYTEA NOT NULL,\
                        VALUE_USD MONEY NOT NULL\
                        )"

tokens_table_query = 'CREATE TABLE TOKENS(\
                        TOKEN_ADDRESS BYTEA NOT NULL,\
                        SYMBOL VARCHAR(50) NOT NULL,\
                        NAME VARCHAR(100) NOT NULL,\
                        DECIMALS SMALLINT NOT NULL\
                        )'

addresses_table_query = 'CREATE TABLE ADDRESSES(\
                            ADDRESS BYTEA NOT NULL,\
                            IS_CONTRACT BOOLEAN NOT NULL,\
                            NICKNAME VARCHAR(100) NOT NULL\
                            )'