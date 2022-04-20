import os
import asyncio
import grpc
from typing import Dict, List
from yrpc_pb2_grpc import YearnExporterStub
from yrpc_pb2 import AddressPrice, GetPriceRequest

NETWORK_ETH = "mainnet"
NETWORK_FTM = "ftm-main"

async def get_prices(exporter, network, addresses: List[Dict[str, str]]):
    request = GetPriceRequest()

    for address in addresses:
        if address["network"] != network:
            continue
        a = request.addresses.add()
        a.address = address["address"]
        a.network = address["network"]

    return exporter.GetPrices(request)


async def main() -> None:
    channels, exporters = _get_channels_exporters()
    addresses = [
        {
            "address": "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e", "network": NETWORK_ETH #YFI
        },
        {
            "address": "0x29b0Da86e484E1C0029B56e817912d778aC0EC69", "network": NETWORK_FTM #YFI
        }
    ]
    for network in exporters:
        async for price in await get_prices(exporters[network], network, addresses):
            print(price)

    for channel in channels:
        await channel.close()


def _get_channels_exporters():
    eth_port = os.getenv("ETH_YRPC_PORT", 1337)
    ftm_port = os.getenv("FTM_YRPC_PORT", 1338)
    eth_channel = _getChannel(eth_port)
    ftm_channel = _getChannel(ftm_port)
    channels = [eth_channel, ftm_channel]

    exporters = {
        NETWORK_ETH: YearnExporterStub(eth_channel),
        NETWORK_FTM: YearnExporterStub(ftm_channel)
    }

    return channels, exporters


def _getChannel(port):
    use_tls = os.getenv("USE_TLS", "false").lower() == "true"
    if use_tls:
        cert_path = os.getenv("TLS_CERT", "yrpc/tls/server-cert.pem")
        creds = grpc.ssl_channel_credentials(open(cert_path, "rb").read())
        return grpc.aio.secure_channel(f"localhost:{port}", creds)
    else:
        return grpc.aio.insecure_channel(f"localhost:{port}")


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
