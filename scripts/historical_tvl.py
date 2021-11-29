import logging
import time
from datetime import datetime, timedelta, timezone
from itertools import count
from brownie import chain

from yearn.db.models import Block, Snapshot, Session, engine, select
from yearn.utils import closest_block_after_timestamp, get_block_timestamp
from yearn.networks import Network
from yearn.yearn import Yearn

logger = logging.getLogger("yearn.historical_tvl")

START_DATE = {
    Network.Mainnet: datetime(2020, 2, 12, tzinfo=timezone.utc),  # first iearn deployment
    Network.Fantom: datetime(2021, 4, 30, tzinfo=timezone.utc),  # ftm vault deployment 2021-09-02
    Network.Arbitrum: datetime(2021, 9, 14, tzinfo=timezone.utc),  # ironbank deployemnt
}


def generate_snapshot_range(start, interval):
    for i in count():
        yield start + i * interval


def main():
    yearn = Yearn(load_strategies=False)
    start = START_DATE[chain.id]
    interval = timedelta(hours=24)

    for snapshot in generate_snapshot_range(start, interval):
        while chain[-1].timestamp < snapshot.timestamp():
            time.sleep(60)

        with Session(engine) as session:
            insert_start = time.perf_counter()

            if session.exec(
                select(Block).where(
                    Block.snapshot == snapshot, Block.chain_id == chain.id
                )
            ).first():
                logger.debug("block exists for snapshot=%s", snapshot)
                continue

            logger.debug("inserting snapshot=%s", snapshot)
            block = closest_block_after_timestamp(snapshot.timestamp())
            assert block is not None, "no block after timestamp found"
            assets = yearn.total_value_at(block)

            new_block = Block(
                chain_id=chain.id,
                height=block,
                timestamp=chain[block].timestamp,
                snapshot=snapshot,
            )
            session.add(new_block)

            for product in assets:
                for name in assets[product]:
                    snap = Snapshot(
                        block=new_block,
                        product=product,
                        name=name,
                        assets=assets[product][name],
                    )
                    session.add(snap)

            session.commit()

            total = sum(sum(x.values()) for x in assets.values())
            elapsed = time.perf_counter() - insert_start
            logger.info(
                f"inserted snapshot={snapshot} block={block:,d} tvl={total:,.0f} in {elapsed:.2f}s"
            )
