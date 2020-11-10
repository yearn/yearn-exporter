import re
import warnings
from dataclasses import dataclass
from typing import Optional, Union

from brownie import accounts, chain, interface, rpc, web3
from brownie.network.contract import InterfaceContainer
from click import secho
from prometheus_client import Gauge, start_http_server

from yearn import constants, curve, uniswap
from yearn.vaults import Vault, load_registry, load_vaults
from yearn import vaults_v2
import toml

warnings.simplefilter("ignore")


def describe_vault(vault: Vault):
    info = {
        "vault balance": vault.vault.balance() / vault.scale,
        "share price": vault.vault.getPricePerFullShare() / 1e18,
        "vault total": vault.vault.totalSupply() / vault.scale,
        "strategy balance": vault.strategy.balanceOf() / vault.scale,
    }

    # some of the oldest vaults don't implement these methods
    if hasattr(vault.vault, "available"):
        info["available"] = vault.vault.available() / vault.scale

    if hasattr(vault.vault, "min") and hasattr(vault.vault, "max"):
        info["strategy buffer"] = vault.vault.min() / vault.vault.max()

    # new curve voter proxy vaults
    if hasattr(vault.strategy, "proxy"):
        vote_proxy = interface.CurveYCRVVoter(vault.strategy.voter())
        swap_func = {"StrategyCurveGUSDProxy": "SWAP"}.get(vault.strategy._name, "curve")
        swap = interface.CurveSwap(getattr(vault.strategy, swap_func)())
        gauge = interface.CurveGauge(vault.strategy.gauge())
        info.update(curve.calculate_boost(gauge, vote_proxy))
        info.update(curve.calculate_apy(gauge, swap))
        info["earned"] = gauge.claimable_tokens.call(vote_proxy).to("ether")

    if hasattr(vault.strategy, "earned"):
        info["lifetime earned"] = vault.strategy.earned() / vault.scale

    if vault.strategy._name == "StrategyYFIGovernance":
        ygov = interface.YearnGovernance(vault.strategy.gov())
        info["earned"] = ygov.earned(vault.strategy) / 1e18
        info["reward rate"] = ygov.rewardRate() / 1e18
        info["ygov balance"] = ygov.balanceOf(vault.strategy) / 1e18
        info["ygov total"] = ygov.totalSupply() / 1e18
        info["token price"] = uniswap.price_router(vault.token, uniswap.usdc)

    return info


def develop():
    registry = load_registry()
    vaults = load_vaults(registry)
    for i, vault in enumerate(vaults):
        secho(vault.name, fg="yellow")
        secho(str(vault), dim=True)
        try:
            info = describe_vault(vault)
            for a, b in info.items():
                print(f"{a} = {b}")
        except ValueError as e:
            print('error', e)


def develop_v2():
    for vault in vaults_v2.VAULTS:
        print(vault)
        print(toml.dumps(vault.describe()))


def exporter_v2():
    vault_gauge = Gauge("yearn_vault", "", ["vault", "param"])
    strat_gauge = Gauge("yearn_strategy", "", ["vault", "strategy", "param"])
    timing = Gauge("yearn_timing", "", ["vault", "action"])
    start_http_server(8801)
    for block in chain.new_blocks():
        secho(f"{block.number}", fg="green")
        for vault in vaults_v2.VAULTS:
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


def exporter():
    prom_gauge = Gauge("yearn", "yearn stats", ["vault", "param"])
    timing = Gauge("yearn_timing", "", ["vault", "action"])
    start_http_server(8800)
    registry = load_registry()
    # load vaults once, todo: update params
    with timing.labels("registry", "load").time():
        vaults = load_vaults(registry)
    for block in chain.new_blocks():
        secho(f"{block.number}", fg="green")
        for vault in vaults:
            with timing.labels(vault.name, "describe").time():
                try:
                    info = describe_vault(vault)
                except ValueError as e:
                    print('error', e)
                    continue
            for param, value in info.items():
                # print(f'{param} = {value}')
                prom_gauge.labels(vault.name, param).set(value)


def audit():
    """
    Audit vault and strategy configuration.
    """
    governance = web3.ens.resolve("ychad.eth")
    registry = load_registry()
    vaults = load_vaults(registry)
    for v in vaults:
        if v.vault.governance() != governance:
            secho(f"{v.name} vault governance == {v.vault.governance()}", fg="red")
            print(f"{v.vault}.setGovernance({governance})")
        if v.strategy.governance() != governance:
            secho(f"{v.name} strategy governance == {v.strategy.governance()}", fg="red")
            print(f"{v.strategy}.setGovernance({governance})")


def harvest():
    assert rpc.is_active()
    andre = accounts.at("andrecronje.eth", force=True)
    print(andre)
    governance = web3.ens.resolve("ychad.eth")
    registry = load_registry()
    vaults = load_vaults(registry)
    for v in vaults:
        secho(v.name, fg="green")
        print(v)
        try:
            tx = v.strategy.harvest({"from": andre})
            tx.info()
        except AttributeError:
            pass
