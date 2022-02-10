import logging
import asyncio
import grpc
import os
from yrpc.yrpc_pb2_grpc import YearnExporterServicer, add_YearnExporterServicer_to_server
from yrpc.yrpc_pb2 import AddressPrice
from yearn.prices import magic

logger = logging.getLogger("YearnExporterServicer")
logging.basicConfig(level=logging.INFO)

class YearnExporter(YearnExporterServicer):

    async def GetPrices(self, request, context):
        for address in request.list:
            yield AddressPrice(address=address, price=magic.get_price(address), unit="USD")

async def serve():
    server = grpc.aio.server()
    add_YearnExporterServicer_to_server(
        YearnExporter(),
        server
    )
    port = os.getenv("YRPC_PORT", 1337)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info(f"YearnExporterServicer listening on port {port}")
    await server.wait_for_termination()
