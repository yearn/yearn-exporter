import asyncio
import grpc
from typing import List
from yrpc_pb2_grpc import YearnExporterStub
from yrpc_pb2 import AddressPrice, Addresses

async def get_address_prices(stub, addresses: List[str]):
    proto_addresses = Addresses()
    proto_addresses.list[:] = addresses
    return stub.GetPrices(proto_addresses)


async def main() -> None:
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.
    async with grpc.aio.insecure_channel('localhost:1337') as channel:
        stub = YearnExporterStub(channel)
        print("-------------- GetPrices --------------")
        addresses = [
            "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e",
            "0x514910771af9ca656af840dff83e8264ecf986ca",
            "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2"
        ]
        async for ap in await get_address_prices(stub, addresses):
            print(ap)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())