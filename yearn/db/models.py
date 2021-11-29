import os
from datetime import datetime
from typing import List, Optional

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


user = os.environ.get('PGUSER', 'postgres')

dsn = f'postgresql://{user}@localhost:5432/yearn'
engine = create_engine(dsn, echo=False)

# SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
