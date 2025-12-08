
import hashlib
import os
from asyncio import gather
from types import ModuleType

import aiofiles
from async_lru import alru_cache


@alru_cache(maxsize=None)
async def hash_module(module: ModuleType) -> bytes:
    is_directory = hasattr(module, '__path__')
    if not is_directory:
        return hashlib.sha256(await read_file(module.__file__)).digest()
    contents = await gather(*(
        read_file(f'{dir}/{file}')
        for path in module.__path__
        for dir, dirs, files in os.walk(path)
        for file in files
    ))
    return hashlib.sha256(b"".join(contents)).digest()
    
async def read_file(file_path: str) -> bytes:
    async with aiofiles.open(file_path, mode='rb') as handle:
        return await handle.read()
