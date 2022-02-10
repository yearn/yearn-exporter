import asyncio
import yrpc
from yrpc.yrpc_server import serve

asyncio.get_event_loop().run_until_complete(serve())
