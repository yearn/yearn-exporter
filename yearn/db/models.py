import os
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

from sqlmodel import (
    Column,
    DateTime,
    Field,
    Relationship,
    Session,
    SQLModel,
    create_engine,
    select,
)

class Event(object):
    isOldApi = False
    event = None
    txn_hash = ""
    multi_harvest = False
    def __init__(self, isOldApi, event, txn_hash):
        self.isOldApi = isOldApi
        self.event = event
        self.txn_hash = txn_hash
        
class Block(SQLModel, table=True):
    id: int = Field(primary_key=True)
    chain_id: int
    height: int
    timestamp: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    snapshot: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True)))

    snapshots: List["Snapshot"] = Relationship(back_populates="block")


class Snapshot(SQLModel, table=True):
    id: int = Field(primary_key=True)
    product: str
    name: str
    assets: float

    block_id: int = Field(foreign_key="block.id")
    block: Block = Relationship(back_populates="snapshots")

class Transactions(SQLModel, table=True):
    txn_hash: str = Field(primary_key=True)
    chain_id: int
    # Transaction fields
    block: int
    txn_to: str
    txn_from: str
    txn_gas_used: int
    txn_gas_price: int
    eth_price_at_block: float
    call_cost_usd: float
    call_cost_eth: float
    kp3r_price_at_block: float
    kp3r_paid: int
    kp3r_paid_usd: float
    keeper_called: bool
    # Date fields
    date: datetime
    date_string: str
    timestamp: str
    updated_timestamp: datetime
    reports: List["Reports"] = Relationship(back_populates="txn")


class Reports(SQLModel, table=True):
    id: int = Field(primary_key=True)
    chain_id: int
    # Transaction fields
    block: int
    txn_hash: str
    txn_hash: str = Field(default=None, foreign_key="transactions.txn_hash")
    txn: Transactions = Relationship(back_populates="reports")
    # StrategyReported fields
    vault_address: str
    strategy_address: str
    gain: int
    loss: int
    debt_paid: int
    total_gain: int
    total_loss: int
    total_debt: int
    debt_added: int
    debt_ratio: int
    # Looked-up fields
    want_token: str
    token_symbol: str
    want_price_at_block: int
    want_gain_usd: int
    gov_fee_in_want: int
    strategist_fee_in_want: int
    gain_post_fees: int
    rough_apr_pre_fee: float
    rough_apr_post_fee: float
    vault_api: str
    vault_name: str
    vault_symbol: str
    vault_decimals: int
    strategy_name: str
    strategy_api: str
    strategist: str
    previous_report_id: int
    multi_harvest: bool
    # Date fields
    date: datetime
    date_string: str
    timestamp: str
    updated_timestamp: datetime
    


pguser = os.environ.get('PGUSER', 'postgres')
pgpassword = os.environ.get('PGPASSWORD', 'yearn')
pghost = os.environ.get('PGHOST', 'localhost')
pgdatabase = os.environ.get('PGDATABASE', 'yearn')
dsn = f'postgresql://{pguser}:{pgpassword}@{pghost}:5432/{pgdatabase}'

user = os.environ.get('POSTGRES_USER')
password = os.environ.get('POSTGRES_PASS')
host = os.environ.get('POSTGRES_HOST')
dsn = f'postgresql://{user}:{password}@{host}:5432/reports'
engine = create_engine(dsn, echo=False)

# SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
