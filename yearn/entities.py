import os
from datetime import datetime
from decimal import Decimal
from functools import cached_property, lru_cache

from brownie import chain
from brownie.network.transaction import TransactionReceipt
from pony.orm import *

db = Database()


class Chain(db.Entity):
    _table_ = "chains"
    chain_dbid = PrimaryKey(int, auto=True)

    chain_name = Required(str, unique=True)
    chainid = Required(int, unique=True)
    victoria_metrics_label = Required(str, unique=True)

    addresses = Set("Address", reverse="chain")
    tokens = Set("Token", reverse="chain")
    user_txs = Set("UserTx")
    treasury_txs = Set("TreasuryTx")
    partners_txs = Set("PartnerHarvestEvent")


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
    chain = Required(Chain, reverse="addresses")

    address = Required(str, index=True)
    nickname = Optional(str)
    is_contract = Required(bool, index=True)
    composite_key(address, chain)
    composite_index(is_contract, chain)

    token = Optional('Token', index=True)
    partners_tx = Set('PartnerHarvestEvent', reverse='wrapper')

    user_tx_from = Set("UserTx", reverse="from_address")
    user_tx_to = Set("UserTx", reverse="to_address")
    treasury_tx_from = Set("TreasuryTx", reverse="from_address")
    treasury_tx_to = Set("TreasuryTx", reverse="to_address")


class Token(db.Entity):
    _table_ = "tokens"
    token_id = PrimaryKey(int, auto=True)
    chain = Required(Chain, index=True)

    symbol = Required(str, index=True)
    name = Required(str)
    decimals = Required(int)

    user_tx = Set('UserTx', reverse="vault")
    treasury_tx = Set('TreasuryTx', reverse="token")
    partner_harvest_event = Set('PartnerHarvestEvent', reverse="vault")
    address = Required(Address, column="address_id")

    @property
    def scale(self) -> int:
        return 10 ** self.decimals


# Used for wallet exporter and other analysis
class UserTx(db.Entity):
    _table_ = "user_txs"
    user_tx_id = PrimaryKey(int, auto=True)
    chain = Required(Chain, index=True)

    timestamp = Required(int, index=True)
    block = Required(int, index=True)
    hash = Required(str, index=True)
    log_index = Required(int)
    composite_key(hash, log_index)
    vault = Required(Token, reverse="user_tx", column="token_id", index=True)
    type = Required(str, index=True)
    from_address = Required(Address, reverse="user_tx_from", column="from", index=True)
    to_address = Required(Address, reverse="user_tx_to", column="to", index=True)
    amount = Required(Decimal,38,18)
    price = Required(Decimal,38,18)
    value_usd = Required(Decimal,38,18)
    gas_used = Required(Decimal,38,1)
    gas_price = Required(Decimal,38,1)



# Treasury tx exporter
class TxGroup(db.Entity):
    _table_ = 'txgroups'
    txgroup_id = PrimaryKey(int, auto=True)

    name = Required(str, unique=True)

    treasury_tx = Set('TreasuryTx', reverse="txgroup")
    parent_txgroup = Optional("TxGroup", reverse="child_txgroups")
    child_txgroups = Set("TxGroup", reverse="parent_txgroup")

    @property
    def top_txgroup(self):
        if self.parent_txgroup is None:
            return self
        return self.parent_txgroup.top_txgroup
    
    @property
    def full_string(self):
        t = self
        retval = t.name
        while True:
            if t.parent_txgroup is None:
                return retval
            t = t.parent_txgroup
            retval = f"{t.name}:{retval}"
            


def get_transaction(txhash: str) -> TransactionReceipt:
    return chain.get_transaction(txhash)

@lru_cache(50)
def get_events(txhash: str):
    return get_transaction(txhash).events

class TreasuryTx(db.Entity):
    _table_ = "treasury_txs"
    treasury_tx_id = PrimaryKey(int, auto=True)
    chain = Required(Chain, index=True)

    timestamp = Required(int, index=True)
    block = Required(int, index=True)
    hash = Required(str, index=True)
    log_index = Optional(int)
    composite_key(hash, log_index)
    token = Required(Token, reverse="treasury_tx", column="token_id", index=True)
    from_address = Required(Address, reverse="treasury_tx_from", column="from", index=True)
    to_address = Optional(Address, reverse="treasury_tx_to", column="to", index=True)
    amount = Required(Decimal,38,18)
    price = Optional(Decimal,38,18)
    value_usd = Optional(Decimal,38,18)
    gas_used = Optional(Decimal,38,1)
    gas_price = Optional(Decimal,38,1)
    txgroup = Required(TxGroup, reverse="treasury_tx", column="txgroup_id", index=True)
    composite_index(chain,txgroup)

    # Helpers
    @cached_property
    def _events(self):
        return self._transaction.events
    
    @cached_property
    def _transaction(self):
        return get_transaction(self.hash)
    
    @property
    def _to_nickname(self):
        if not self.to_address:
            return None
        return self.to_address.nickname
    
    @property
    def _from_nickname(self):
        return self.from_address.nickname
    
    @property
    def _symbol(self):
        return self.token.symbol



# Caching for partners_summary.py
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
    wrapper = Required(Address, reverse='partners_tx', index=True) # we use `Address` instead of `Token` because some partner wrappers are unverified
    vault = Required(Token, index=True)

    chain = Required(Chain, index=True)
    composite_index(chain, vault, wrapper)
    

db.bind(
    provider="postgres",
    user=os.environ.get("PGUSER", "postgres"),
    host=os.environ.get("PGHOST", "127.0.0.1"),
    password=os.environ.get("PGPASSWORD", ""),
    database=os.environ.get("PGDATABASE", "postgres"),
)
    
db.generate_mapping(create_tables=True)


@db_session
def create_txgroup_parentage_view() -> None:
    try:
        db.execute(
            """
            CREATE VIEW txgroup_parentage as
            SELECT a.txgroup_id,
                COALESCE(d.name,c.name, b.name, a.name) top_level_account,
                CASE WHEN d.name is not null THEN c.name when c.name is not null THEN b.name when b.name IS not NULL THEN a.name else null end subaccount1,
                CASE when d.name is not null THEN b.name when c.name IS not NULL THEN a.name else null end subaccount2,
                CASE when d.name IS not NULL THEN a.name else null end subaccount3
            FROM txgroups a
            LEFT JOIN txgroups b ON a.parent_txgroup = b.txgroup_id
            LEFT JOIN txgroups c ON b.parent_txgroup = c.txgroup_id
            LEFT JOIN txgroups d ON c.parent_txgroup = d.txgroup_id
            """
        )
    except ProgrammingError as e:
        if str(e).strip() != 'relation "txgroup_parentage" already exists':
            raise

@db_session
def create_general_ledger_view() -> None:
    try:
        db.execute(
            """
            create VIEW general_ledger as
            SELECT b.chain_name, TO_TIMESTAMP(a.timestamp) AS timestamp, a.block, a.hash, a.log_index, c.symbol AS token, d.address AS "from", d.nickname as from_nickname, e.address AS "to", e.nickname as to_nickname, a.amount, a.price, a.value_usd, f.name AS txgroup, g.name AS parent_txgroup
            FROM treasury_txs a
                LEFT JOIN chains b ON a.chain = b.chain_dbid
                LEFT JOIN tokens c ON a.token_id = c.token_id
                LEFT JOIN addresses d ON a."from" = d.address_id
                LEFT JOIN addresses e ON a."to" = e.address_id
                LEFT JOIN txgroups f ON a.txgroup_id = f.txgroup_id
                LEFT JOIN txgroups g ON f.parent_txgroup = g.txgroup_id
            ORDER BY TO_TIMESTAMP(a.timestamp)
            """
        )
    except ProgrammingError as e:
        if str(e).strip() != 'relation "general_ledger" already exists':
            raise
    
@db_session
def create_unsorted_txs_view() -> None:
    try:
        db.execute(
            """
            CREATE VIEW unsorted_txs as
            SELECT *
            FROM general_ledger
            WHERE txgroup = 'Categorization Pending'
            ORDER BY TIMESTAMP desc
            """
        )
    except ProgrammingError as e:
        if str(e).strip() != 'relation "unsorted_txs" already exists':
            raise

@db_session
def create_treasury_time_averages_view() -> None:
    try:
        db.execute(
            """
            CREATE VIEW treasury_time_averages AS
            WITH base AS (
                SELECT gs as DATE, a.NAME AS txgroup, b.name as parent_txgroup, b.txgroup_id AS parent_txgroup_id
                FROM txgroups a
                LEFT JOIN txgroups b ON a.parent_txgroup = b.txgroup_id
                LEFT JOIN generate_series('2020-07-21', '2022-09-03', interval '1 day') gs ON 1=1
            ), summed AS (
                SELECT DATE,
                    coalesce(sum(value_usd), 0) daily_total,
                    a.txgroup,
                    a.parent_txgroup,
                    a.parent_txgroup_id
                FROM base a
                left join general_ledger b ON date = CAST(TIMESTAMP AS DATE) and a.txgroup = b.txgroup AND a.parent_txgroup = b.parent_txgroup
                GROUP BY date, a.txgroup, a.parent_txgroup, a.parent_txgroup_id
            )
            SELECT *,
                sum(daily_total) OVER (partition BY txgroup, parent_txgroup ORDER BY date ROWS 6 PRECEDING) / 7 average_7d,
                sum(daily_total) OVER (partition BY txgroup, parent_txgroup ORDER BY date ROWS 13 PRECEDING) / 14 average_14d,
                sum(daily_total) OVER (partition BY txgroup, parent_txgroup ORDER BY date ROWS 29 PRECEDING) / 30 average_30d,
                sum(daily_total) OVER (partition BY txgroup, parent_txgroup ORDER BY date ROWS 89 PRECEDING) / 90 average_90d
            FROM summed
            ORDER BY DATE
            """
        )
    except ProgrammingError as e:
        if str(e).strip() != 'relation "treasury_time_averages" already exists':
            raise

def create_views() -> None:
    create_txgroup_parentage_view()
    create_general_ledger_view()
    create_unsorted_txs_view()
    create_treasury_time_averages_view()

create_views()
