from collections import defaultdict

from cachetools.func import ttl_cache
from fastapi import FastAPI

from yearn.entities import Snapshot, db_session, select

app = FastAPI(title="Yearn Exporter")
tree = lambda: defaultdict(tree)


@ttl_cache(600)
def get_daily_tvl():
    with db_session:
        return select(
            (snap.block.snapshot.date(), sum(snap.assets)) for snap in Snapshot
        ).order_by(1)[:]


@ttl_cache(600)
def get_daily_tvl_detailed():
    data = tree()
    with db_session:
        for timestamp, product, name, assets in select(
            (snap.block.snapshot.date(), snap.product, snap.name, snap.assets) for snap in Snapshot
        ).order_by(1):
            if assets > 0:
                data[timestamp][product][name] = assets
    return data


@app.get("/v1/tvl", name="tvl")
def read_daily_tvl():
    """Daily historical TVL snapshot."""
    return get_daily_tvl()


@app.get("/v1/tvl/detailed", name="tvl detailed")
def read_daily_tvl_detailed():
    """Detailed daily historical TVL snapshot broken down by product and contract."""
    return get_daily_tvl_detailed()
