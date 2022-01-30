import os
from datetime import datetime
from decimal import Decimal

from pony.orm import *

db = Database()


class Block(db.Entity):
    _table_ = "blocks"
    block_id = PrimaryKey(int, auto=True)

    block = Required(int, unique=True)
    timestamp = Required(datetime, sql_type="timestamptz")
    snapshot = Optional(datetime, sql_type="timestamptz")

    snapshots = Set("Snapshot")


class Snapshot(db.Entity):
    _table_ = "snapshots"
    snapshot_id = PrimaryKey(int, auto=True)

    block = Required(Block)
    product = Required(str)
    name = Required(str)
    assets = Required(float)
    delegated = Optional(float)  # to be filled later


class Address(db.Entity):
    _table_ = "addresses"
    address_id = PrimaryKey(int, auto=True)

    chainid = Required(int)
    address = Required(str)
    composite_key(chainid, address)

    is_contract = Required(bool)
    nickname = Optional(str)

    token = Optional('Token')


class Token(db.Entity):
    _table_ = "tokens"
    token_id = PrimaryKey(int, auto=True)

    symbol = Required(str)
    name = Required(str)
    decimals = Required(int)

    user_tx = Set('UserTx', reverse="vault")
    partners_tx = Set('PartnerHarvestEvent', reverse="wrapper")
    address = Required(Address, column="address_id")


class UserTx(db.Entity):
    _table_ = "user_txs"
    user_tx_id = PrimaryKey(int, auto=True)

    timestamp = Required(int)
    block = Required(int)
    hash = Required(str)
    log_index = Required(int)
    composite_key(hash, log_index)
    vault = Required(Token, reverse="user_tx", column="token_id")
    type = Required(str)
    from_address = Required(str, column="from")
    to_address = Required(str, column="to")
    amount = Required(Decimal,38,18)
    price = Required(Decimal,38,18)
    value_usd = Required(Decimal,38,18)
    gas_used = Required(Decimal,38,1)
    gas_price = Required(Decimal,38,1)



class PartnerHarvestEvent(db.Entity):
    _table_ = 'partners_txs'
    partner_id = PrimaryKey(int, auto=True)
    
    block = Required(int)
    timestamp = Required(int)
    balance = Required(Decimal,38,18)
    total_supply = Required(Decimal,38,18)
    vault_price = Required(Decimal,38,18)
    balance_usd = Required(Decimal,38,18)
    share = Required(Decimal,38,18)
    payout_base = Required(Decimal,38,18)
    protocol_fee = Required(Decimal,38,18)
    wrapper = Required(Token, reverse='partners_tx')
    vault = Required(str)
    

db.bind(
    provider="postgres",
    user=os.environ.get("POSTGRES_USER", "postgres"),
    host=os.environ.get('POSTGRES_HOST',"127.0.0.1"),
    password=os.environ.get("POSTGRES_PASS", "yearn-exporter"),
    database="postgres",
)

db.generate_mapping(create_tables=True)
