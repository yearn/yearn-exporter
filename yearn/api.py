from collections import defaultdict

from cachetools.func import ttl_cache
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from yearn.entities import Snapshot, db_session, select

app = FastAPI(title="Yearn Exporter")
app.add_middleware(CORSMiddleware, allow_origins=["*"])
tree = lambda: defaultdict(tree)
ALLOWED_HOURLY_RESOLUTION = {1, 2, 4, 6, 8, 12, 24}


@ttl_cache(600)
def get_aggregated_tvl_data(hourly_resolution):
    with db_session:
        return select(
            (snap.block.snapshot, sum(snap.assets))
            for snap in Snapshot
            if int(snap.block.snapshot.hour) % hourly_resolution == 0
        ).order_by(1)[:]


@ttl_cache(600)
def get_latest_tvl_data():
    with db_session:
        return select((s.block.snapshot, sum(s.assets)) for s in Snapshot).order_by(-1).first()


@ttl_cache(600)
def get_detailed_tvl_data(hourly_resolution):
    data = tree()
    with db_session:
        for timestamp, product, name, assets in select(
            (snap.block.snapshot, snap.product, snap.name, snap.assets)
            for snap in Snapshot
            if int(snap.block.snapshot.hour) % hourly_resolution == 0
        ).order_by(1):
            if assets > 0:
                data[timestamp][product][name] = assets
    return data


@app.get("/v1/tvl", name="tvl")
def read_daily_tvl(hourly_resolution: int = 24):
    """Daily historical TVL snapshot."""
    if hourly_resolution not in ALLOWED_HOURLY_RESOLUTION:
        raise HTTPException(400, f"hourly_resolution must be {ALLOWED_HOURLY_RESOLUTION}")
    return get_aggregated_tvl_data(hourly_resolution)


@app.get("/v1/tvl/latest", name="tvl latest")
def read_latest_tvl():
    """Latest hourly TVL snapshot."""
    data = get_latest_tvl_data()
    return {"date": data[0], "tvl": data[1]}


@app.get("/v1/tvl/detailed", name="tvl detailed")
def read_daily_tvl_detailed(hourly_resolution: int = 24):
    """Detailed daily historical TVL snapshot broken down by product and contract."""
    if hourly_resolution not in ALLOWED_HOURLY_RESOLUTION:
        raise HTTPException(400, f"hourly_resolution must be {ALLOWED_HOURLY_RESOLUTION}")
    return get_detailed_tvl_data(hourly_resolution)
