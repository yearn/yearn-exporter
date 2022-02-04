from typing import List
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from brownie_bridge.client import send
import logging
app = FastAPI()

logger = logging.getLogger(__name__)

# TODO use constants from yearn.networks which currently breaks a lot of things
bridge_hosts = {
  1: 'brownie-bridge-eth',
  250: 'brownie-bridge-ftm',
  42161: 'brownie-bridge-arb'
}

@app.get("/v2/{chain_id}/prices")
async def prices(chain_id: int, a: List[str] = Query(None), type: str = "json"):
    if not a or len(a) == 0:
        raise HTTPException(status_code=400, detail="no addresses specified")
    if chain_id not in bridge_hosts.keys():
        raise HTTPException(status_code=400, detail="unsupported network specified")
    if not type or type not in ["jsonl", "json"]:
        logger.debug("incorrect type specified, defaulting to json")
        type = "json"

    request = {
      "function": "get_price",
      "type": type,
      "data": a
    }
    return StreamingResponse(
      _bridge_streamer(request, bridge_hosts[chain_id])
    )


async def _bridge_streamer(request, host):
    async for response in send(request, host):
        yield response
