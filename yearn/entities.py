import os
import typing
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import cached_property, lru_cache

from brownie import Contract, chain
from brownie.network.transaction import TransactionReceipt
from pony.orm import *

from yearn.treasury.constants import BUYER
from yearn.utils import closest_block_after_timestamp, contract

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
    streams_from = Set("Stream", reverse="from_address")
    streams_to = Set("Stream", reverse="to_address")
    streams = Set("Stream", reverse="contract")


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
    streams = Set('Stream', reverse="token")

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
    streams = Set("Stream", reverse="txgroup")

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


v3_multisig = "0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7"

class Stream(db.Entity):
    _table_ = 'streams'
    stream_id = PrimaryKey(str)

    contract = Required(Address, reverse="streams")
    start_block = Required(int)
    end_block = Optional(int)
    token = Required(Token, reverse='streams', index=True)
    from_address = Required(Address, reverse='streams_from')
    to_address = Required(Address, reverse='streams_to')
    amount_per_second = Required(Decimal, 38, 1)
    status = Required(str, default="Active")
    txgroup = Optional(TxGroup, reverse="streams")

    streamed_funds = Set("StreamedFunds")
    
    # NOTE Streams always use 20 decimals
    scale = int(1e20)

    @property
    def is_alive(self) -> bool:
        if self.end_block is None:
            assert self.status in ["Active", "Paused"]
            return self.status == "Active"
        assert self.status == "Stopped"
        return False
    
    @property
    def amount_per_minute(self) -> int:
        return self.amount_per_second * 60

    @property
    def amount_per_hour(self) -> int:
        return self.amount_per_minute * 60

    @property
    def amount_per_day(self) -> int:
        return self.amount_per_hour * 24

    def stop_stream(self, block: int) -> None:
        self.end_block = block
        self.status = "Stopped"
    
    def pause(self) -> None:
        self.status = "Paused"
    
    @classmethod
    def get_or_create_entity(cls, log) -> "Stream":
        if len(log.values()) == 4: # StreamCreated
            from_address, to_address, amount_per_second, stream_id = log.values()
        elif len(log.values()) == 7: # StreamModified
            from_address, _, _, _, to_address, amount_per_second, stream_id = log.values()
        else:
            raise NotImplementedError("This is not an appropriate event log.")
        
        stream_id = stream_id.hex()

        try:
            return Stream[stream_id]
        except ObjectNotFound:
            from yearn.outputs.postgres.utils import (cache_address,
                                                      cache_token,
                                                      cache_txgroup)

            txgroup = {
                BUYER: "Top-up Buyer Contract",
                v3_multisig: "V3 Development",
            }.get(to_address, "Other Grants")

            txgroup = cache_txgroup(txgroup)
            stream_contract = cache_address(log.address)
            token = cache_token(contract(log.address).token())
            from_address = cache_address(from_address)
            to_address = cache_address(to_address)

            entity = Stream(
                stream_id = stream_id,
                contract = stream_contract,
                start_block = log.block_number,
                token = token,
                from_address = from_address,
                to_address = to_address,
                amount_per_second = amount_per_second,
                txgroup = txgroup,
            )
            commit()
            return entity
    
    @property
    def stream_contract(self) -> Contract:
        return contract(self.contract.address)
    
    def start_timestamp(self, block: typing.Optional[int] = None) -> int:
        return int(self.stream_contract.streamToStart('0x' + self.stream_id, block_identifier=block))

    def amount_withdrawable(self, block: int):
        return self.stream_contract.withdrawable.call(
            self.from_address.address,
            self.to_address.address,
            int(self.amount_per_second),
            block_identifier = block,
        )
    
    def print(self):
        symbol = self.token.symbol
        print(f'{symbol} per second: {self.amount_per_second / self.scale}')
        print(f'{symbol} per day: {self.amount_per_day / self.scale}')

one_day = 60 * 60 * 24

class StreamedFunds(db.Entity):
    _table_ = "streamed_funds"

    date = Required(date)
    stream = Required(Stream, reverse="streamed_funds")
    PrimaryKey(stream, date)

    amount = Required(Decimal, 38, 18)
    price = Required(Decimal, 38, 18)
    value_usd = Required(Decimal, 38, 18)
    seconds_active = Required(int)

    @classmethod
    def get_or_create_entity(cls, stream: Stream, date: datetime) -> "StreamedFunds":
        if entity := StreamedFunds.get(date=date, stream=stream):
            return entity

        check_at = date + timedelta(days=1) - timedelta(seconds=1)
        block = closest_block_after_timestamp(check_at.timestamp())
        start_timestamp = stream.start_timestamp(block)
        if start_timestamp == 0:
            print("Stream cancelled. Must handle.")
            return
        
        seconds_active = int(check_at.timestamp()) - start_timestamp
        seconds_active_today = seconds_active if seconds_active < one_day else one_day
        amount_streamed_today = stream.amount_per_second * seconds_active_today / stream.scale
        
        # We only need this for this function so we import in this function to save time where this function isn't needed.
        from yearn.prices import magic

        price = Decimal(magic.get_price(stream.token.address.address, block))

        return StreamedFunds(
            date = date,
            stream = stream, 
            amount = amount_streamed_today,
            price = price,
            value_usd = amount_streamed_today * price,
            seconds_active = seconds_active_today,
        )    

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
def create_stream_ledger_view() -> None:
    """
    Prepares daily stream data with the same structure as general_ledger view so we can combine them with a union.
    """

    try:
        db.execute(
            """
            create view stream_ledger as
            SELECT  'Mainnet' as chain_name,
                    cast(DATE AS timestamp) as timestamp,
                    NULL as block, 
                    NULL as hash, 
                    NULL as log_index, 
                    symbol as token, 
                    d.address AS "from", 
                    d.nickname as from_nickname, 
                    e.address as "to", 
                    e.nickname as to_nickname, 
                    amount, 
                    price, 
                    value_usd, 
                    txgroup.name as txgroup, 
                    parent.name as parent_txgroup, 
                    txgroup.txgroup_id
            FROM streamed_funds a
                LEFT JOIN streams b ON a.stream = b.stream_id
                LEFT JOIN tokens c ON b.token = c.token_id
                LEFT JOIN addresses d ON b.from_address = d.address_id
                LEFT JOIN addresses e ON b.to_address = e.address_id
                LEFT JOIN txgroups txgroup ON b.txgroup = txgroup.txgroup_id
                LEFT JOIN txgroups parent ON txgroup.parent_txgroup = parent.txgroup_id
            """
        )
    except ProgrammingError as e:
        if str(e).strip() != 'relation "stream_ledger" already exists':
            raise


@db_session
def create_general_ledger_view() -> None:
    try:
        db.execute(
            """
            create VIEW general_ledger as
            select *
            from (
                SELECT b.chain_name, TO_TIMESTAMP(a.timestamp) AS timestamp, a.block, a.hash, a.log_index, c.symbol AS token, d.address AS "from", d.nickname as from_nickname, e.address AS "to", e.nickname as to_nickname, a.amount, a.price, a.value_usd, f.name AS txgroup, g.name AS parent_txgroup, f.txgroup_id
                FROM treasury_txs a
                    LEFT JOIN chains b ON a.chain = b.chain_dbid
                    LEFT JOIN tokens c ON a.token_id = c.token_id
                    LEFT JOIN addresses d ON a."from" = d.address_id
                    LEFT JOIN addresses e ON a."to" = e.address_id
                    LEFT JOIN txgroups f ON a.txgroup_id = f.txgroup_id
                    LEFT JOIN txgroups g ON f.parent_txgroup = g.txgroup_id
                UNION
                SELECT chain_name, TIMESTAMP, cast(block AS integer) block, hash, CAST(log_index AS integer) as log_index, token, "from", from_nickname, "to", to_nickname, amount, price, value_usd, txgroup, parent_txgroup, txgroup_id
                FROM stream_ledger
            ) a
            ORDER BY timestamp
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
                SELECT gs as DATE, txgroup_id, token
                FROM (
                    SELECT DISTINCT grp.txgroup_id, gl.token
                    FROM txgroups grp
                    LEFT JOIN general_ledger gl ON grp.txgroup_id = gl.txgroup_id
                ) a
                LEFT JOIN generate_series('2020-07-21', CURRENT_DATE, interval '1 day') gs ON 1=1
            ), summed AS (
                SELECT DATE,
                    a.txgroup_id,
                    a.token,
                    coalesce(sum(value_usd), 0) daily_total
                FROM base a
                left join general_ledger b ON date = CAST(TIMESTAMP AS DATE) and a.txgroup_id = b.txgroup_id AND a.token = b.token
                GROUP BY date, a.txgroup_id, a.token
            )

            SELECT *,
                sum(daily_total) OVER (partition BY txgroup_id, token ORDER BY date ROWS 6 PRECEDING) / 7 average_7d,
                sum(daily_total) OVER (partition BY txgroup_id, token ORDER BY date ROWS 13 PRECEDING) / 14 average_14d,
                sum(daily_total) OVER (partition BY txgroup_id, token ORDER BY date ROWS 29 PRECEDING) / 30 average_30d,
                sum(daily_total) OVER (partition BY txgroup_id, token ORDER BY date ROWS 89 PRECEDING) / 90 average_90d
            FROM summed
            ORDER BY DATE
            """
        )
    except ProgrammingError as e:
        if str(e).strip() != 'relation "treasury_time_averages" already exists':
            raise

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
        

def create_views() -> None:
    create_txgroup_parentage_view()
    create_stream_ledger_view()
    create_general_ledger_view()
    create_unsorted_txs_view()
    create_treasury_time_averages_view()

create_views()
