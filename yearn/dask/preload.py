
import os
import sys

import nest_asyncio

nest_asyncio.apply()

# Ensure `app` can be found on path so objects can deserialize
if "/" not in sys.path:
    sys.path.insert(0, "/")
# Ensure yearn module is reachable
if (path := os.path.abspath('.')) not in sys.path:
    sys.path.insert(0, path)
