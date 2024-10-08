
import asyncio

import logging

from yearn.entities import create_views
from yearn.treasury import streams

logger = logging.getLogger(__name__)

create_views()

def main():
    asyncio.run(streams._get_coro())
