import asyncio
import os
import orjson
import logging
logger = logging.getLogger(__name__)

BRIDGE_PORT = os.getenv("BRIDGE_PORT", 1337)
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "127.0.0.1")

async def send(request, host=BRIDGE_HOST):
    reader, writer = await asyncio.open_connection(host, BRIDGE_PORT)
    message = orjson.dumps(request)

    logger.debug("send: %s", message.decode())
    writer.write(message)
    writer.write(b"\n")
    await writer.drain()

    while True:
        data = await reader.readline()
        if data:
            decoded = data.decode()
            logger.debug("received: %s", decoded)
            if decoded == "yAmazing":
                logger.debug("yAmazing! all data consumed")
                break
            else:
                yield decoded
        else:
            await asyncio.sleep(0.1)

    logger.debug("closing the connection")
    writer.close()
