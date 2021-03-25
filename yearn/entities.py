import os
from datetime import datetime
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


db.bind(
    provider="postgres",
    user=os.environ.get("PGUSER", "postgres"),
    host=os.environ.get("PGHOST", "127.0.0.1"),
    database="yearn",
)

db.generate_mapping(create_tables=True)
