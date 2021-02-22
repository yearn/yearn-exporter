import warnings
from collections import Counter

import toml
from brownie import chain
from brownie.exceptions import BrownieEnvironmentWarning
from click import secho, style
from prometheus_client import Gauge, start_http_server

from yearn import iearn, vaults_v1, vaults_v2, ironbank

warnings.simplefilter("ignore", BrownieEnvironmentWarning)


def develop_v1():
    registry = vaults_v1.load_registry()
    vaults = vaults_v1.load_vaults(registry)
    for i, vault in enumerate(vaults):
        secho(vault.name, fg="yellow")
        secho(str(vault), dim=True)
        info = vault.describe()
        for a, b in info.items():
            print(f"{a} = {b}")


def exporter_v1():
    prom_gauge = Gauge("yearn", "yearn stats", ["vault", "param"])
    timing = Gauge("yearn_timing", "", ["vault", "action"])
    start_http_server(8800)
    registry = vaults_v1.load_registry()
    # load vaults once, todo: update params
    with timing.labels("registry", "load").time():
        vaults = vaults_v1.load_vaults(registry)
    for block in chain.new_blocks():
        secho(f"{block.number}", fg="green")
        for vault in vaults:
            with timing.labels(vault.name, "describe").time():
                try:
                    info = vault.describe()
                except ValueError as e:
                    print("error", e)
                    continue
            for param, value in info.items():
                # print(f'{param} = {value}')
                prom_gauge.labels(vault.name, param).set(value)


def develop_v2():
    for vault in vaults_v2.get_vaults():
        print(vault)
        print(toml.dumps(vault.describe()))


def exporter_v2():
    vault_gauge = Gauge("yearn_vault", "", ["vault", "param"])
    strat_gauge = Gauge("yearn_strategy", "", ["vault", "strategy", "param"])
    timing = Gauge("yearn_timing", "", ["vault", "action"])
    start_http_server(8801)
    vaults = vaults_v2.get_vaults()
    for block in chain.new_blocks():
        secho(f"{block.number}", fg="green")
        for vault in vaults:
            secho(vault.name)
            with timing.labels(vault.name, "describe").time():
                info = vault.describe()

            for param, value in info.items():
                if param == "strategies":
                    continue
                vault_gauge.labels(vault.name, param).set(value)

            for strat in info["strategies"]:
                for param, value in info["strategies"][strat].items():
                    strat_gauge.labels(vault.name, strat, param).set(value)


def develop_experimental():
    for vault in vaults_v2.get_experimental_vaults():
        print(vault)
        print(toml.dumps(vault.describe()))


def exporter_experimental():
    vault_gauge = Gauge("yearn_vault", "", ["vault", "param"])
    strat_gauge = Gauge("yearn_strategy", "", ["vault", "strategy", "param"])
    timing = Gauge("yearn_timing", "", ["vault", "action"])
    start_http_server(8802)
    experimental_vaults = vaults_v2.get_experimental_vaults()
    for block in chain.new_blocks():
        secho(f"{block.number}", fg="green")
        for vault in experimental_vaults:
            secho(vault.name)
            with timing.labels(vault.name, "describe").time():
                info = vault.describe()

            for param, value in info.items():
                if param == "strategies":
                    continue
                vault_gauge.labels(vault.name, param).set(value)

            for strat in info["strategies"]:
                for param, value in info["strategies"][strat].items():
                    strat_gauge.labels(vault.name, strat, param).set(value)
