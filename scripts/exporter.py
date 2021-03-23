import json

from brownie import chain

from yearn.outputs import prometheus
from yearn.yearn import Yearn


def main():
    prometheus.start(8800)
    yearn = Yearn()
    for block in chain.new_blocks():
        data = yearn.describe()
        # export to prometheus
        prometheus.export(data)
        # save to file
        with open("research/describe.json", "wt") as f:
            json.dump(data, f, indent=2)


def tvl():
    yearn = Yearn()
    for block in chain.new_blocks():
        data = yearn.total_value_at()
        total = sum(sum(vaults.values()) for vaults in data.values())
        print(f"block={block.number} tvl={total}")
        # save to file
        with open("research/tvl.json", "wt") as f:
            json.dump(data, f, indent=2)
