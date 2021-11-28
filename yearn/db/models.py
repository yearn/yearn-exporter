import os
from typing import Optional
from sqlmodel import Field, SQLModel, create_engine, Column, DateTime, Session, select
from datetime import datetime


class Block(SQLModel, table=True):
    chain_id: int
    block: int = Field(primary_key=True)
    timestamp: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    snapshot: Optional[datetime] = Field(sa_column=Column(DateTime(timezone=True)))


class Snapshot(SQLModel, table=True):
    id: int = Field(primary_key=True)
    chain_id: int
    block: int = Field(foreign_key="block.block")
    product: str
    name: str
    assets: float


user = os.environ.get('PGUSER', 'postgres')

dsn = f'postgresql://{user}@localhost:5432/yearn'
engine = create_engine(dsn, echo=False)

# SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
