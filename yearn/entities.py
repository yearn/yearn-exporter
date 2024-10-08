import os
import typing
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import cached_property, lru_cache

from brownie import chain
from brownie.network.event import _EventItem
from brownie.network.transaction import TransactionReceipt
from cachetools.func import ttl_cache
from pony.orm import *
from y import Contract, get_price
from y.time import closest_block_after_timestamp
from y.contracts import contract_creation_block
from y.utils.events import decode_logs, get_logs_asap

from yearn.treasury.constants import BUYER
from yearn.utils import dates_between

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
    vesting_escrows = Set("VestingEscrow", reverse="address")
    vests_received = Set("VestingEscrow", reverse="recipient")
    vests_funded = Set("VestingEscrow", reverse="funder")


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
    vesting_escrows = Set("VestingEscrow", reverse="token")

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
    vesting_escrows = Set("VestingEscrow", reverse="txgroup")

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
            

@lru_cache(10)
def get_transaction(txhash: str) -> TransactionReceipt:
    return chain.get_transaction(txhash)

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
    from_address = Optional(Address, reverse="treasury_tx_from", column="from", index=True)
    to_address = Optional(Address, reverse="treasury_tx_to", column="to", index=True)
    amount = Required(Decimal,38,18)
    price = Optional(Decimal,38,18)
    value_usd = Optional(Decimal,38,18)
    gas_used = Optional(Decimal,38,1)
    gas_price = Optional(Decimal,38,1)
    txgroup = Required(TxGroup, reverse="treasury_tx", column="txgroup_id", index=True)
    composite_index(chain,txgroup)

    # Helpers
    @property
    def _events(self):
        return self._transaction.events
    
    @property
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
    reason = Optional(str)
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
    def get_or_create_entity(cls, log: _EventItem) -> "Stream":
        if log.name == "StreamCreated":
            from_address, to_address, amount_per_second, stream_id = log.values()
            reason = None
        elif log.name == "StreamCreatedWithReason":
            from_address, to_address, amount_per_second, stream_id, reason = log.values()
        elif log.name == "StreamModified":
            from_address, _, _, old_stream_id, to_address, amount_per_second, stream_id = log.values()
            reason = Stream[old_stream_id.hex()].reason
        else:
            raise NotImplementedError("This is not an appropriate event log.")
        
        stream_id = stream_id.hex()

        try:
            return Stream[stream_id]
        except ObjectNotFound:
            from yearn.outputs.postgres.utils import (address_dbid,
                                                      token_dbid,
                                                      cache_txgroup)

            txgroup = {
                BUYER: "Top-up Buyer Contract",
                v3_multisig: "V3 Development",
            }.get(to_address, "Other Grants")

            txgroup = cache_txgroup(txgroup)
            stream_contract = address_dbid(log.address)
            token = token_dbid(Contract(log.address).token())
            from_address = address_dbid(from_address)
            to_address = address_dbid(to_address)

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
            if reason is not None:
                entity.reason = reason
            commit()
            return entity
    
    @property
    def stream_contract(self) -> Contract:
        return Contract(self.contract.address)
    
    @property
    def start_date(self) -> date:
        return datetime.fromtimestamp(chain[self.start_block].timestamp).date()

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

class StreamedFunds(db.Entity):
    """ Each object represents one calendar day of tokens streamed for a particular stream. """
    _table_ = "streamed_funds"

    date = Required(date)
    stream = Required(Stream, reverse="streamed_funds")
    PrimaryKey(stream, date)

    amount = Required(Decimal, 38, 18)
    price = Required(Decimal, 38, 18)
    value_usd = Required(Decimal, 38, 18)
    seconds_active = Required(int)
    is_last_day = Required(bool)
    
    @db_session
    def get_entity(stream_id: str, date: datetime) -> "StreamedFunds":
        stream = Stream[stream_id]
        return StreamedFunds.get(date=date, stream=stream)

    @classmethod
    @db_session
    def create_entity(cls, stream_id: str, date: datetime, price, seconds_active: int, is_last_day: bool) -> "StreamedFunds":
        stream = Stream[stream_id]
        # How much was streamed on `date`?
        amount_streamed_today = round(stream.amount_per_second * seconds_active / stream.scale, 18)
        entity = StreamedFunds(
            date = date,
            stream = stream, 
            amount = amount_streamed_today,
            price = round(price, 18),
            value_usd = round(amount_streamed_today * price, 18),
            seconds_active = seconds_active,
            is_last_day = is_last_day,
        )
        return entity

@ttl_cache(ttl=60)
def _get_rug_pull(address: str) -> typing.Optional[_EventItem]:
    logs = get_logs_asap(address, None)
    decoded = decode_logs(logs)
    for event in decoded:
        if event.name == "RugPull":
            return event

class VestingEscrow(db.Entity):
    _table_ = 'vesting_escrows'
    escrow_id = PrimaryKey(int, auto=True)

    address = Required(Address, reverse='vesting_escrows', unique=True)
    funder = Required(Address, reverse='vests_funded')
    recipient = Required(Address, reverse='vests_received')
    token = Required(Token, reverse='vesting_escrows')
    amount = Required(Decimal, 38, 18)
    start_timestamp = Required(datetime)
    end_timestamp = Required(datetime)
    duration = Required(int)
    cliff_length = Required(int)
    rugged = Required(bool, default=False)
    txgroup = Optional(TxGroup, reverse="vesting_escrows")
    _rugged_at = Optional(datetime)
    _rugged_on = Optional(date)

    vested_funds = Set("VestedFunds", reverse="escrow")

    @cached_property
    def contract(self) -> Contract:
        return Contract(self.address.address)
    
    def dates(self) -> typing.List[date]:
        return [
            dt.date()
            for dt in dates_between(self.start_timestamp, self.end_timestamp)
            if self.rugged_on is None or dt.date() <= self.rugged_on
        ]
    
    @cached_property
    def deploy_block(self) -> int:
        return contract_creation_block(self.address.address)
    
    def amortize_vested_funds(self) -> None:
        for date in self.dates():
            try:
                VestedFunds.get_or_create_entity(self, date)
            except VestNotActive as e:
                print(e)
    
    @lru_cache
    def get_rug_pull(self) -> typing.Optional[_EventItem]:
        return _get_rug_pull(self.address.address)
    
    @property
    def rugged_at(self) -> typing.Optional[datetime]:
        if not self._rugged_at and (rug := self.get_rug_pull()):
            self._rugged_at = datetime.fromtimestamp(
                int(chain[rug.block_number].timestamp)
            )
        return self._rugged_at
    
    @property
    def rugged_on(self) -> typing.Optional[date]:
        if not self._rugged_on and self.rugged_at:
            self._rugged_on = self.rugged_at.date()
        return self._rugged_on

    @staticmethod
    def get_or_create_entity(event: _EventItem) -> "VestingEscrow":
        from yearn.outputs.postgres.utils import address_dbid, cache_token

        print(event)
        funder, token, recipient, escrow, amount, start, duration, cliff_length = event.values()
        escrow_address_dbid = address_dbid(escrow)
        escrow = VestingEscrow.get(address=escrow_address_dbid)
        if escrow is None:
            token_entity = cache_token(token)
            escrow = VestingEscrow(
                address = escrow_address_dbid,
                funder = address_dbid(funder),
                recipient = address_dbid(recipient),
                token = token_entity,
                amount = amount / token_entity.scale,
                start_timestamp = datetime.fromtimestamp(start),
                duration = duration,
                end_timestamp = datetime.fromtimestamp(start + duration),
                cliff_length = cliff_length,
            )
            commit()
        return escrow
    
    def total_vested_at_block(self, block: int) -> Decimal:
        try:
            vested = Decimal(
                self.contract.unclaimed(block_identifier=block) + self.contract.total_claimed(block_identifier=block)
            )
            return vested / self.token.scale
        except ValueError as e:
            if str(e) == "No data was returned - the call likely reverted" and block < self.deploy_block:
                print(f'escrow {self.address.address} not yet deployed')
                return Decimal(0)
            raise e
    
    def total_vested_thru_date(self, date: "date") -> Decimal:
        try:
            return VestedFunds.get_or_create_entity(self, date).total_vested
        except VestNotActive:
            return Decimal(0)


class VestNotActive(Exception):
    ...

class VestedFunds(db.Entity):
    _table_ = "vested_funds"
    vested_funds_id = PrimaryKey(int, auto=True)

    escrow = Required(VestingEscrow, reverse="vested_funds")
    date = Required(date)
    composite_key(escrow, date)
    amount = Required(Decimal, 38, 18)
    price = Required(Decimal, 38, 18)
    value_usd = Required(Decimal, 38, 18)
    total_vested = Required(Decimal, 38, 18)
    checked_at_timestamp = Required(datetime)
    checked_at_block = Required(int)
        
    @staticmethod
    def get_or_create_entity(escrow: VestingEscrow, date: "date"):
        check_at = datetime(date.year, date.month, date.day) + timedelta(days=1) - timedelta(seconds=1)
        if check_at < escrow.start_timestamp:
            raise VestNotActive(f"[{date}] Vesting for {escrow.address.address} starts on {escrow.start_timestamp.date()}.")
        
        if escrow.rugged_on and date > escrow.rugged_on:
            raise VestNotActive(f"[{date}] Vesting escrow {escrow.address.address} was rugged on {escrow.rugged_on}")

        entity = VestedFunds.get(escrow=escrow, date=date)
        if entity is None:
            block = closest_block_after_timestamp(check_at)
            total_unlocked = escrow.total_vested_at_block(block)
            total_unlocked_yesterday = escrow.total_vested_thru_date(date - timedelta(days=1))
            unlocked_today = total_unlocked - total_unlocked_yesterday
            price = Decimal(get_price(escrow.token.address.address, block))

            entity = VestedFunds(
                escrow = escrow,
                date = date,
                amount = round(unlocked_today, 18),
                price = round(price, 18),
                value_usd = round(unlocked_today * price, 18),
                total_vested = round(total_unlocked, 18),
                checked_at_timestamp = check_at,
                checked_at_block = block,
            )
            commit()

        print(date)
        print(f"{entity.amount}   {entity.total_vested}")
        return entity


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
def deduplicate_internal_transfers():
    db.execute(
        """
        WITH counted AS (
            SELECT treasury_tx_id, ROW_NUMBER() over(partition BY CHAIN, TIMESTAMP, block, hash, log_index, token_id, "from", "to", amount, gas_used, gas_price ORDER BY treasury_tx_id ASC) number
            FROM treasury_txs
        )
        DELETE FROM treasury_txs WHERE treasury_tx_id IN (
            SELECT treasury_tx_id FROM counted WHERE NUMBER > 1
        )
        """
    )
    
# views
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
def create_vesting_ledger_view() -> None:
    db.execute("""
        DROP VIEW IF EXISTS vesting_ledger CASCADE;
        CREATE VIEW vesting_ledger AS
        SELECT  d.chain_name, 
            CAST(date AS timestamp) AS "timestamp",
            cast(NULL as int) AS block,
            NULL AS "hash",
            cast(NULL as int) AS "log_index",
            c.symbol AS "token",
            e.address AS "from",
            e.nickname as from_nickname,
            f.address AS "to",
            f.nickname as to_nickname,
            a.amount,
            a.price,
            a.value_usd,
            g.name as txgroup,
            h.name AS parent_txgroup,
            g.txgroup_id
        FROM vested_funds a 
        LEFT JOIN vesting_escrows b ON a.escrow = b.escrow_id
        LEFT JOIN tokens c ON b.token = c.token_id
        LEFT JOIN chains d ON c.chain = d.chain_dbid
        LEFT JOIN addresses e ON b.address = e.address_id
        LEFT JOIN addresses f ON b.recipient = f.address_id
        LEFT JOIN txgroups g ON b.txgroup = g.txgroup_id
        left JOIN txgroups h ON g.parent_txgroup = h.txgroup_id
    """)


@db_session
def create_general_ledger_view() -> None:
    db.execute(
        """
        drop VIEW IF EXISTS general_ledger CASCADE;
        create VIEW general_ledger as
        select *
        from (
            SELECT treasury_tx_id, b.chain_name, TO_TIMESTAMP(a.timestamp) AS timestamp, a.block, a.hash, a.log_index, c.symbol AS token, d.address AS "from", d.nickname as from_nickname, e.address AS "to", e.nickname as to_nickname, a.amount, a.price, a.value_usd, f.name AS txgroup, g.name AS parent_txgroup, f.txgroup_id
            FROM treasury_txs a
                LEFT JOIN chains b ON a.chain = b.chain_dbid
                LEFT JOIN tokens c ON a.token_id = c.token_id
                LEFT JOIN addresses d ON a."from" = d.address_id
                LEFT JOIN addresses e ON a."to" = e.address_id
                LEFT JOIN txgroups f ON a.txgroup_id = f.txgroup_id
                LEFT JOIN txgroups g ON f.parent_txgroup = g.txgroup_id
            UNION
            SELECT -1, chain_name, TIMESTAMP, cast(block AS integer) block, hash, CAST(log_index AS integer) as log_index, token, "from", from_nickname, "to", to_nickname, amount, price, value_usd, txgroup, parent_txgroup, txgroup_id
            FROM stream_ledger
            UNION
            SELECT -1, *
            FROM vesting_ledger
        ) a
        ORDER BY timestamp
        """
    )
    
@db_session
def create_unsorted_txs_view() -> None:
    db.execute(
        """
        DROP VIEW IF EXISTS unsorted_txs CASCADE;
        CREATE VIEW unsorted_txs as
        SELECT *
        FROM general_ledger
        WHERE txgroup = 'Categorization Pending'
        ORDER BY TIMESTAMP desc
        """
    )

@db_session
def create_treasury_time_averages_view() -> None:
    db.execute(
        """
        DROP VIEW IF EXISTS treasury_time_averages CASCADE;
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

@db_session
def create_txgroup_parentage_view() -> None:
    db.execute(
        """
        DROP VIEW IF EXISTS txgroup_parentage CASCADE;
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
        

def create_views() -> None:
    create_txgroup_parentage_view()
    create_stream_ledger_view()
    create_vesting_ledger_view()
    create_general_ledger_view()
    create_unsorted_txs_view()
    create_treasury_time_averages_view()

create_views()
