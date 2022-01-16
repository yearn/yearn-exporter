import os
from datetime import datetime
from decimal import Decimal

from pony.orm import *

db = Database()


class Block(db.Entity):
    _table_ = "blocks"

    block = PrimaryKey(int)
    timestamp = Required(datetime, sql_type="timestamptz")
    snapshot = Optional(datetime, sql_type="timestamptz")

    snapshots = Set("Snapshot")


class Snapshot(db.Entity):
    _table_ = "snapshots"

    block = Required(Block)
    product = Required(str)
    name = Required(str)
    assets = Required(float)
    delegated = Optional(float)  # to be filled later


class Address(db.Entity):
    _table_ = "addresses"

    chainid = Required(int)
    address = Required(str)
    PrimaryKey(chainid,address)
    is_contract = Required(bool)
    nickname = Optional(str)

    token = Optional('Token')


class Token(db.Entity):
    _table_ = "tokens"

    token = PrimaryKey(Address, columns=["chainid",'token_address'])
    symbol = Required(str)
    name = Required(str)
    decimals = Required(int)

    user_tx = Set('UserTx', reverse="vault")
    #treasury_tx = Set('TreasuryTx', reverse="token")


class UserTx(db.Entity):
    _table_ = "user_txs"

    timestamp = Required(int)
    block = Required(int)
    hash = Required(str)
    log_index = Required(int)
    vault = Required(Token, columns=["chainid","vault"], reverse="user_tx")
    type = Required(str)
    from_address = Required(str, column="from")
    to_address = Required(str, column="to")
    amount = Required(Decimal,38,18)
    price = Required(Decimal,38,18)
    value_usd = Required(Decimal,38,18)
    gas_used = Required(Decimal,38,1)
    gas_price = Required(Decimal,38,1)

    PrimaryKey(hash,log_index)

'''
class TreasuryTx(db.Entity):
    _table_ = "treasury_txs"

    #chainid = Required(int)
    timestamp = Required(int)
    block = Required(int)
    hash = Required(str)
    log_index = Required(int)
    token = Required(Token, columns=["chainid","token"], reverse="treasury_tx")
    type = Required(str)
    from_address = Required(str, column="from")
    to_address = Required(str, column="to")
    amount = Required(Decimal)
    price = Required(Decimal)
    value_usd = Required(Decimal)
    gas_used = Required(Decimal)
    gas_price = Required(Decimal)

    PrimaryKey(hash,log_index)
'''

db.bind(
    provider="postgres",
    user=os.environ.get("PGUSER", "postgres"),
    host=os.environ.get("PGHOST", "postgres"),
    password=os.environ.get("PGPASS", "yearn-exporter"),
    database="postgres",
)

db.generate_mapping(create_tables=True)
