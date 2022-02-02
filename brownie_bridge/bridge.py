import orjson
import asyncio
import logging
import os

from brownie_bridge.functions.price import get_price
logger = logging.getLogger(__name__)

BRIDGE_PORT = os.getenv("BRIDGE_PORT", 1337)
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "127.0.0.1")

func_map = {
    "get_price": get_price
}

async def start_bridge():
    server = await asyncio.start_server(
        handle_server_request, BRIDGE_HOST, BRIDGE_PORT)

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    logger.info("Brownie Bridge 🍪🌉 is ready and listening on %s", addrs)

    async with server:
        await server.serve_forever()


async def handle_server_request(reader, writer):
    data = await reader.readline()
    message = data.decode()
    addr = writer.get_extra_info('peername')
    logger.info("received %s from %s", message, addr)

    payload = orjson.loads(message)
    function = payload["function"]
    data = payload["data"]
    func = func_map[function]
    if payload["type"] == "jsonl":
        await stream_json(writer, func, data)
    else:
        await write_json(writer, func, data)
    writer.write("yAmazing".encode())
    await writer.drain()
    logger.debug("closing the connection")
    writer.close()


async def stream_json(writer, func, data):
    for d in data:
        entry = orjson.dumps(func(d))
        logger.debug(entry.decode())
        writer.write(entry)
        writer.write(b"\n")
        await writer.drain()


async def write_json(writer, func, data):
    response = orjson.dumps([ func(d) for d in data ])
    logger.debug(response.decode())
    writer.write(response)
    writer.write(b"\n")
    await writer.drain()
