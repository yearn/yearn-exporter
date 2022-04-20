import logging
import asyncio
import grpc
import os
from yrpc.yrpc_pb2_grpc import YearnExporterServicer, add_YearnExporterServicer_to_server
from yrpc.yrpc_pb2 import AddressPrice
from yearn.prices import magic
from brownie import network, chain

logger = logging.getLogger("yRPC")
logging.basicConfig(level=logging.INFO)

class YearnExporter(YearnExporterServicer):

    async def GetPrices(self, request, context):
        chain_id = chain.id
        for a in request.addresses:
            yield AddressPrice(
                address=a.address,
                price=magic.get_price(a.address),
                chain_id=chain_id,
                denominator="USD"
            )

async def serve():
    server = grpc.aio.server()
    add_YearnExporterServicer_to_server(
        YearnExporter(),
        server
    )
    port = os.getenv("YRPC_PORT", 1337)
    use_tls = os.getenv("USE_TLS", "false").lower() == "true"
    if use_tls:
        server.add_secure_port(f"[::]:{port}", _getCredentials())
    else:
        server.add_insecure_port(f"[::]:{port}")

    await server.start()
    logger.info(f"yRPC listening on port {port}")
    await server.wait_for_termination()


def _getCredentials():
    key_path = os.getenv("TLS_KEY", "/app/yearn-exporter/tls/server-key.pem")
    cert_path = os.getenv("TLS_CERT", "/app/yearn-exporter/tls/server-cert.pem")
    private_key = open(key_path, "rb").read()
    certificate_chain = open(cert_path, "rb").read()
    return grpc.ssl_server_credentials(
        [ (private_key, certificate_chain) ]
    )
