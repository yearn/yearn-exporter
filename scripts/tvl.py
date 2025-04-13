import warnings

import sentry_sdk
from brownie.exceptions import BrownieEnvironmentWarning
from click import style
from eth_utils.toolz import groupby
from tabulate import tabulate
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','tvl')

warnings.simplefilter("ignore", BrownieEnvironmentWarning)


def main():
    data = []
    yearn = Yearn()

    for product, registry in yearn.registries.items():
        for name, tvl in registry.total_value_at().items():
            data.append({"product": product, "name": name, "tvl": tvl})

    data.sort(key=lambda x: -x["tvl"])
    print(tabulate(data, floatfmt=",.0f"))

    products = groupby(lambda x: x["product"], data)
    tvl_by_product = {a: sum(x["tvl"] for x in b) for a, b in products.items()}
    table = [
        *tvl_by_product.items(),
        [style("total", fg="yellow"), sum(tvl_by_product.values())],
        [style("final", fg="green", bold=True), sum(tvl_by_product.values())],
    ]
    print(tabulate(table, headers=["product", "tvl"], floatfmt=",.0f"))
