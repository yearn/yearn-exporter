import warnings
from collections import Counter

from brownie.exceptions import BrownieEnvironmentWarning
from click import secho, style

from yearn import iearn, ironbank, vaults_v1, vaults_v2

warnings.simplefilter("ignore", BrownieEnvironmentWarning)


def main():
    totals = Counter()
    deduct = Counter()
    # iearn
    secho("iearn", fg="cyan", bold=True)
    earns = iearn.load_iearn()
    output = iearn.describe_iearn(earns)
    for name, info in output.items():
        totals["iearn"] += info["tvl"]
        print(style(f'${info["tvl"]:12,.0f}', fg="green"), style(f"{name}", fg="yellow"))

    print(style(f"${totals['iearn']:12,.0f}", fg="green", bold=True), style(f"total", fg="yellow", bold=True))

    # vaults v1
    secho("v1", fg="cyan", bold=True)
    registry = vaults_v1.load_registry()
    vaults = vaults_v1.load_vaults(registry)
    for vault in vaults:
        info = vault.describe()
        totals["v1"] += info["tvl"]
        print(style(f'${info["tvl"]:12,.0f}', fg="green"), style(f"{vault.name}", fg="yellow"))
        if vault.name in ["curve.fi/y", "curve.fi/busd"]:
            deduct[vault.name] += info["tvl"]

    print(style(f"${totals['v1']:12,.0f}", fg="green", bold=True), style(f"total", fg="yellow", bold=True))

    # vaults v2
    secho("v2", fg="cyan", bold=True)
    vaults = vaults_v2.get_vaults()
    for vault in vaults:
        info = vault.describe()
        if "tvl" not in info:
            print(style("error".rjust(13), fg="red"), style(f"{vault.name}", fg="yellow"))
            continue
        totals["v2"] += info["tvl"]
        print(style(f'${info["tvl"]:12,.0f}', fg="green"), style(f"{vault.name}", fg="yellow"))

    print(style(f"${totals['v2']:12,.0f}", fg="green", bold=True), style(f"total", fg="yellow", bold=True))

    # ironbank
    secho("ironbank", fg="cyan", bold=True)
    earns = ironbank.load_ironbank()
    output = ironbank.describe_ironbank(earns)
    for name, info in output.items():
        totals["ironbank"] += info["tvl"]
        print(style(f'${info["tvl"]:12,.0f}', fg="green"), style(f"{name}", fg="yellow"))

    print(style(f"${totals['ironbank']:12,.0f}", fg="green", bold=True), style(f"total", fg="yellow", bold=True))

    # tally
    print(style(f"${sum(totals.values()):12,.0f}", fg="green", bold=True), style(f"total tvl", fg="yellow", bold=True))
    print(style(f"${sum(deduct.values()):12,.0f}", fg="red", bold=True), style(f"duplicate", fg="yellow", bold=True))
    print(
        style(f"${sum(totals.values()) - sum(deduct.values()):12,.0f}", fg="green", bold=True),
        style(f"final tvl", fg="green", bold=True),
    )
