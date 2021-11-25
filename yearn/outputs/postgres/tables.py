
treasury_table_query = f'CREATE TABLE TREASURY_TXS(\
                            CHAINID SMALLINT NOT NULL,\
                            TIMESTAMP INT NOT NULL,\
                            BLOCK INT NOT NULL,\
                            HASH CHAR(66) NOT NULL,\
                            "from" CHAR(42) NOT NULL,\
                            "to" CHAR(42) NOT NULL,\
                            TOKEN CHAR(42) NOT NULL,\
                            AMOUNT DECIMAL(38,18) NOT NULL,\
                            PRICE MONEY NOT NULL,\
                            VALUE_USD MONEY NOT NULL,\
                            GAS_USED DECIMAL(38,0),\
                            GAS_PRICE BIGINT,\
                            CONSTRAINT fk_from\
                                FOREIGN KEY ("from",CHAINID)\
                                    REFERENCES addresses(ADDRESS,CHAINID),\
                            CONSTRAINT fk_to\
                                FOREIGN KEY ("to",CHAINID)\
                                    REFERENCES addresses(ADDRESS,CHAINID),\
                            CONSTRAINT fk_token\
                                FOREIGN KEY (TOKEN,CHAINID)\
                                    REFERENCES tokens(TOKEN_ADDRESS,CHAINID)\
                            )'

users_table_query = f'CREATE TABLE USER_TXS(\
                        CHAINID SMALLINT NOT NULL,\
                        TIMESTAMP INT NOT NULL,\
                        BLOCK INT NOT NULL,\
                        HASH CHAR(66) NOT NULL,\
                        LOG_INDEX SMALLINT NOT NULL,\
                        VAULT CHAR(42) NOT NULL,\
                        TYPE VARCHAR(10) NOT NULL,\
                        "from" CHAR(42) NOT NULL,\
                        "to" CHAR(42) NOT NULL,\
                        AMOUNT DECIMAL(38,18) NOT NULL,\
                        PRICE MONEY NOT NULL,\
                        VALUE_USD MONEY NOT NULL,\
                        GAS_USED DECIMAL(38,0),\
                        GAS_PRICE DECIMAL(38,0),\
                        CONSTRAINT fk_from\
                            FOREIGN KEY ("from",CHAINID)\
                                REFERENCES addresses(ADDRESS,CHAINID),\
                        CONSTRAINT fk_to\
                            FOREIGN KEY ("to",CHAINID)\
                                REFERENCES addresses(ADDRESS,CHAINID),\
                        CONSTRAINT fk_vault\
                            FOREIGN KEY (VAULT,CHAINID)\
                                REFERENCES addresses(ADDRESS,CHAINID)\
                        )'

tokens_table_query = 'CREATE TABLE TOKENS(\
                        CHAINID SMALLINT NOT NULL,\
                        TOKEN_ADDRESS CHAR(42) NOT NULL,\
                        SYMBOL VARCHAR(50) NOT NULL,\
                        NAME VARCHAR(100) NOT NULL,\
                        DECIMALS SMALLINT NOT NULL,\
                        PRIMARY KEY (CHAINID, TOKEN_ADDRESS),\
                        CONSTRAINT fk_token_address\
                            FOREIGN KEY (TOKEN_ADDRESS,CHAINID)\
                                REFERENCES addresses(ADDRESS,CHAINID)\
                        )'

addresses_table_query = 'CREATE TABLE ADDRESSES(\
                            CHAINID SMALLINT NOT NULL,\
                            ADDRESS CHAR(42) NOT NULL,\
                            IS_CONTRACT BOOLEAN NOT NULL,\
                            NICKNAME VARCHAR(100),\
                            PRIMARY KEY (CHAINID, ADDRESS)\
                            )'