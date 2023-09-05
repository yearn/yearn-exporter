from datetime import datetime

import click
import sentry_sdk
from brownie.utils.output import build_tree

sentry_sdk.set_tag('script','print_strategies')


def main():
    from yearn.v2.registry import Registry
    registry = Registry()
    print(registry)
    registry.load_strategies()
    tree = []
    for vault in registry.vaults:
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
        for strategy in vault.strategies + vault.revoked_strategies:
            config = vault.vault.strategies(strategy.strategy).dict()
            color = 'green' if strategy in vault.strategies else 'red'
            strategies.append([
                f'{config.get("debtRatio", 0) / 10000:.2%} ' + click.style(strategy.name, fg=color) + f' {strategy.strategy}',
                *[f'{k} = {transforms[k](v)}' for k, v in config.items()]
            ])
        tree.append([
            click.style(vault.name, fg='green', bold=True) + f' {vault.vault}',
            *strategies,
        ])

    print(build_tree(tree))
