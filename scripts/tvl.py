import warnings
from collections import Counter
from tabulate import tabulate

from brownie.exceptions import BrownieEnvironmentWarning
from click import secho, style
from toolz import groupby

from yearn import iearn, ironbank, vaults_v1
import yearn.v2.registry

warnings.simplefilter("ignore", BrownieEnvironmentWarning)


def main():
    data = []

    # iearn
    iearn_registry = iearn.Registry()
    for name, tvl in iearn_registry.total_value_at().items():
        data.append({"product": "iearn", "name": name, "tvl": tvl})

    # vaults v1
    v1_registry = vaults_v1.Registry()
    for name, tvl in v1_registry.total_value_at().items():
        data.append({"product": "v1", "name": name, "tvl": tvl})

    # vaults v2
    v2_registry = yearn.v2.registry.Registry()
    for name, tvl in v2_registry.total_value_at().items():
        data.append({"product": "v2", "name": name, "tvl": tvl})

    # ironbank
    ib = ironbank.Registry()
    for name, tvl in ib.total_value_at().items():
        data.append({"product": "ib", "name": name, "tvl": tvl})

    data.sort(key=lambda x: -x["tvl"])
    print(tabulate(data, floatfmt=",.0f"))

    products = groupby(lambda x: x["product"], data)
    tvl_by_product = {a: sum(x["tvl"] for x in b) for a, b in products.items()}
    duplicate = sum(x["tvl"] for x in data if x["name"] in ["curve.fi/busd", "curve.fi/y"])
    table = [
        *tvl_by_product.items(),
        ["__duplicate__", duplicate],
        ["__total__", sum(tvl_by_product.values())],
        ["__final__", sum(tvl_by_product.values()) - duplicate],
    ]
    print(tabulate(table, headers=["product", "tvl"], floatfmt=",.0f"))
