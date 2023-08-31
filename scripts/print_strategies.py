import asyncio
from datetime import datetime

import click
import sentry_sdk
from brownie.utils.output import build_tree
from multicall.utils import await_awaitable

sentry_sdk.set_tag('script','print_strategies')


def main():
    from yearn.v2.registry import Registry
    registry = Registry()
    print(registry)
    tree = []
    for vault in await_awaitable(registry.vaults):
        transforms = {
            'performanceFee': lambda bps: f'{bps / 10000:.2%}',
            'activation': lambda ts: datetime.utcfromtimestamp(ts),
            'debtRatio': lambda bps: f'{bps / 10000:.2%}',
            'debtLimit': lambda tokens: f'{tokens / vault.scale if tokens != 2**256-1 else "unlimited"}',
            'minDebtPerHarvest': lambda tokens: f'{tokens / vault.scale}',
            'lastReport': lambda ts: datetime.utcfromtimestamp(ts),
            'maxDebtPerHarvest': lambda tokens: f'{tokens / vault.scale if tokens != 2**256-1 else "unlimited"}',
            'rateLimit': lambda tokens: f'{tokens / vault.scale if tokens != 2**256-1 else "unlimited"}/s',
            'totalDebt': lambda tokens: f'{tokens / vault.scale}',
            'totalGain': lambda tokens: f'{tokens / vault.scale}',
            'totalLoss': lambda tokens: f'{tokens / vault.scale}',
        }
        strategies = []
        strats, revoked_strats = await_awaitable(asyncio.gather(vault.strategies, vault.revoked_strategies))
        for strategy in strats + revoked_strats:
            config = vault.vault.strategies(strategy.strategy).dict()
            color = 'green' if strategy in strats else 'red'
            strategies.append([
                f'{config.get("debtRatio", 0) / 10000:.2%} ' + click.style(strategy.name, fg=color) + f' {strategy.strategy}',
                *[f'{k} = {transforms[k](v)}' for k, v in config.items()]
            ])
        tree.append([
            click.style(vault.name, fg='green', bold=True) + f' {vault.vault}',
            *strategies,
        ])

    print(build_tree(tree))
