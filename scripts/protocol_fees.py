import json
import pickle
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

from brownie import ZERO_ADDRESS, Contract, web3, chain
from click import secho, style
from toolz import concat, groupby, unique, valmap
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.events import decode_logs, get_logs_asap
from yearn.prices import magic
from yearn.traces import decode_traces, get_traces
from yearn.utils import get_block_timestamp
from yearn.v2.registry import Registry
from yearn.v2.vaults import Vault
from semantic_version import Version
from pprint import pprint
from pytest import approx
from yearn.multicall2 import fetch_multicall
from functools import wraps
import click
from collections import Counter
from tabulate import tabulate
import atexit
import os


def v1():
    # 1
    controllers = [
        '0x2be5D998C95DE70D9A38b3d78e49751F10F9E88b',
        '0x31317F9A5E4cC1d231bdf07755C994015A96A37c',
        '0x9E65Ad11b299CA0Abefc2799dDB6314Ef2d91080',
    ]
    path = Path('research/traces/01-controllers.json')
    if not path.exists():
        traces = get_traces([], controllers)
        json.dump(traces, path.open('wt'), indent=2)
    else:
        traces = json.load(path.open())

    # 2
    path = Path('research/traces/02-controllers-decode.json')
    if not path.exists():
        decoded = decode_traces(traces)
        json.dump(decoded, path.open('wt'), indent=2)
    else:
        decoded = json.load(path.open())

    # 3
    token_to_strategies = defaultdict(list)
    strategies = []
    token_to_vault = {}
    for x in decoded:
        if x['func'] == 'setStrategy(address,address)':
            if x['args'][1] == ZERO_ADDRESS:
                continue
            token_to_strategies[x['args'][0]].append(x['args'][1])
            strategies.append(x['args'][1])
        if x['func'] == 'setVault(address,address)':
            token_to_vault[x['args'][0]] = x['args'][1]

    secho(f'found {len(strategies)} strategies across {len(token_to_vault)} vaults', fg='bright_green')
    # 4
    path = Path('research/traces/03-strategies.json')
    if not path.exists():
        strategy_traces = get_traces([], strategies)
        json.dump(strategy_traces, path.open('wt'), indent=2)
    else:
        strategy_traces = json.load(path.open())

    # 5
    path = Path('research/traces/04-strategies-decode.json')
    if not path.exists():
        strategy_decoded = decode_traces(strategy_traces)
        json.dump(strategy_decoded, path.open('wt'), indent=2)
    else:
        strategy_decoded = json.load(path.open())

    # 6
    rewards = {x['args'][0] for x in decoded if x['func'] == 'setRewards(address)'}
    strategists = {x['args'][0] for x in strategy_decoded if x['func'] == 'setStrategist(address)'}
    print(style('rewards:', fg='bright_green'), ', '.join(rewards))
    print(style('strategists:', fg='bright_green'), ', '.join(strategists))

    # 7
    path = Path('research/traces/05-logs.pickle')
    if not path.exists():
        abi = {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
                {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
                {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
            ],
            "name": "Transfer",
            "type": "event",
        }
        topics = construct_event_topic_set(
            abi, web3.codec, {"from": sorted(strategies), "to": sorted(rewards | strategists)}
        )
        logs = get_logs_asap(sorted(token_to_vault), topics, from_block=0, verbose=1)
        pickle.dump(logs, path.open('wb'))
    else:
        logs = pickle.load(path.open('rb'))

    secho(f'{len(logs)} logs', fg='bright_green')

    # 8
    withdrawals = {x['tx_hash'] for x in strategy_decoded if x['func'] == 'withdraw(uint256)'}
    harvests = {x['tx_hash'] for x in strategy_decoded if x['func'] == 'harvest()'}
    funcs = {x['tx_hash']: x['func'] for x in strategy_decoded}
    secho(f'{len(withdrawals)} withdrawals, {len(harvests)} harvests')
    fees = []
    scales = {}
    print('decoding logs')
    logs_by_block = groupby('blockNumber', logs)

    def process_harvest(log):
        log = decode_logs([log])[0]
        sender, receiver, amount = log.values()
        if amount == 0:
            return None

        if log.address not in scales:
            scales[log.address] = 10 ** Contract(log.address).decimals()

        fee_type = 'unknown'
        if log.transaction_hash.hex() in harvests:
            fee_type = 'harvest'
        if log.transaction_hash.hex() in withdrawals:
            fee_type = 'withdrawal'

        fee_dest = 'unknown'
        if receiver in rewards:
            fee_dest = 'rewards'
        if receiver in strategists:
            fee_dest = 'strategist'

        price = magic.get_price(log.address, log.block_number)
        func = funcs.get(log.transaction_hash.hex(), 'unknown')
        return {
            'block_number': log.block_number,
            'timestamp': get_block_timestamp(log.block_number),
            'transaction_hash': log.transaction_hash.hex(),
            'vault': token_to_vault[log.address],
            'token': log.address,
            'strategy': sender,
            'recipient': receiver,
            'fee_type': fee_type,
            'fee_dest': fee_dest,
            'func': func,
            'token_price': price,
            'amount_native': amount / scales[log.address],
            'amount_usd': price * amount / scales[log.address],
        }

    fees = [x for x in tqdm(ThreadPoolExecutor().map(process_harvest, logs), total=len(logs)) if x]

    path = Path('research/traces/06-fees.json')
    json.dump(fees, path.open('wt'), indent=2)


def fetch_vault_rewards(vault):
    if 'UpdateRewards' in vault.vault.topics:
        return [
            x['rewards'] for x in decode_logs(get_logs_asap(str(vault.vault), [vault.vault.topics['UpdateRewards']]))
        ]
    else:
        return [vault.vault.rewards()]


## debug
times = Counter()
counts = Counter()
reconciliation = Counter()


def profile(f):
    @wraps(f)
    def inner(*args, **kwds):
        start = perf_counter()
        result = f(*args, **kwds)
        eta = perf_counter() - start
        click.secho(f'{f.__name__} took {eta:.3f}s', fg='bright_blue')
        times[f.__name__] += eta
        counts[f.__name__] += 1
        return result

    return inner


def profile_summary():
    header = ['func', 'cum_time', 'call_count', 'avg_time']
    data = [[f, times[f], counts[f], times[f] / counts[f]] for f in times]
    print(tabulate(data, headers=header))

    print()
    print(f'{reconciliation=}')


atexit.register(profile_summary)


@profile
def assess_fees(vault: Vault, report):
    MAX_BPS = 10_000
    api_version = Version(vault.api_version)
    block_timestamp = get_block_timestamp(report.block_number)

    
    SECS_PER_YEAR = 31_556_952
    if api_version < Version('0.3.3'):
        SECS_PER_YEAR = 31_557_600
    
    management_bps, performance_bps = fetch_multicall(
        [vault.vault, 'managementFee'],
        [vault.vault, 'performanceFee'],
        block=report.block_number,
    )
    last_report, strategies, price_per_share = fetch_multicall(
        [vault.vault, 'lastReport'],
        [vault.vault, 'strategies', report['strategy']],
        [vault.vault, 'pricePerShare'],
        block=report.block_number - 1,
    )

    # total debt
    if api_version <= Version('0.3.0'):
        total_debt = vault.vault.totalAssets()
    elif api_version <= Version('0.3.3'):
        total_debt = vault.vault.totalDebt()
    elif api_version <= Version('0.3.4'):
        total_debt, delegated_assets = fetch_multicall(
            [vault.vault, 'totalDebt'],
            [vault.vault, 'delegatedAssets'],
            block=report.block_number - 1,
        )
        total_debt -= delegated_assets
    elif api_version <= Version('0.3.5'):
        total_debt = strategies['totalDebt']
        delegated_assets = Contract(report['strategy']).delegatedAssets(block_identifier=report.block_number - 1)
        total_debt -= delegated_assets
    
    management_fee = (total_debt * (block_timestamp - last_report) * management_bps) / MAX_BPS / SECS_PER_YEAR
    strategist_fee = (report['gain'] * strategies['performanceFee']) / MAX_BPS
    performance_fee = report['gain'] * performance_bps / MAX_BPS
    
    total_fee = management_fee + strategist_fee + performance_fee
    if api_version > Version('0.3.5') and total_fee > report['gain']:
        management_fee = report['gain'] - performance_fee - strategist_fee

    return {
        'block_number': report.block_number,
        'timestamp': block_timestamp,
        'transaction_hash': report.transaction_hash,
        'vault': str(vault.vault),
        'strategy': report['strategy'],
        'gain': report['gain'] / vault.scale,
        'loss': report['loss'] / vault.scale,
        'duration': block_timestamp - last_report,
        'total_debt': total_debt / vault.scale,
        'price_per_share': price_per_share / vault.scale,
        'management_fee': management_fee / price_per_share,
        'performance_fee': performance_fee / price_per_share,
        'strategist_fee': strategist_fee / price_per_share,
        'treasury_fee': (management_fee + performance_fee) / price_per_share,
    }


@profile
def reconcile(vault, ass, check):
    if check is None:
        print_status('no events', False)
    
    elif len(check) == 2:
        rec = ass["strategist_fee"] == approx(check[0]["value"] / vault.scale, rel=1e-3)
        reconciliation[rec] += 1
        print_status(
            f'strategist {ass["strategist_fee"]} got {check[0]["value"] / vault.scale}',
            rec
        )

        rec = ass["treasury_fee"] == approx(check[1]["value"] / vault.scale, rel=1e-3)
        reconciliation[rec] += 1
        print_status(
            f'protocol {ass["treasury_fee"]} got {check[1]["value"] / vault.scale}',
            rec
        )
    else:
        rec = ass["treasury_fee"] == approx(check[0]["value"] / vault.scale, rel=1e-3)
        reconciliation[rec] += 1
        print_status(
            f'protocol {ass["treasury_fee"]} got {check[0]["value"] / vault.scale}',
            rec
        )


def print_status(message, status):
    color = {True: 'green', False: 'red'}[status]
    sym = {True: '✔︎', False: '✗'}[status]
    click.secho(f'{sym} {message}', fg=color)


def get_protocol_fees(vault):
    vault.load_strategies()
    rewards = fetch_vault_rewards(vault)

    # older strategies missed migration events, so we rely on StrategyRerported
    strategies_from_reports = valmap(len, groupby('strategy', vault._reports))
    print('known reports:', strategies_from_reports)
    
    strategies = list(strategies_from_reports)

    targets = [str(x) for x in unique(rewards + strategies)]
    print(strategies)

    # use gains to separate management fees from performance fees
    gains = {x.transaction_hash: x['gain'] for x in vault._reports}

    # fees are paid by issuing new vault shares
    topics = construct_event_topic_set(
        filter_by_name('Transfer', vault.vault.abi)[0],
        web3.codec,
        {'sender': str(vault.vault), 'receiver': targets},
    )
    logs = decode_logs(get_logs_asap(str(vault.vault), topics))
    logs_by_tx = groupby(lambda x: x.transaction_hash, logs)
    # print(len(logs), len(logs_by_tx))

    fees = []
    # progress = tqdm(vault._reports, desc=vault.name.ljust(20)[:20])

    MAX_BPS = 10_000
    SECS_PER_YEAR = 31_556_952

    strategies_from_reports = valmap(len, groupby('strategy', vault._reports))
    print(strategies_from_reports)

    for report in vault._reports[-5:]:
        click.secho(f"[{report.block_number}] {dict(report)}\ntx={report.transaction_hash.hex()}", fg='bright_blue')
        ass = assess_fees(vault, report)
        click.secho(f'{ass}', fg='yellow')
        reconcile(vault, ass, logs_by_tx.get(report.transaction_hash))
        continue
        vault_strategies = vault.vault.strategies(report['strategy'], block_identifier=report.block_number - 1)
        last_report = vault_strategies['lastReport']
        duration = get_block_timestamp(report.block_number) - last_report
        print(last_report, duration)
        if report['gain'] == 0:
            continue

        strategy = Contract(report['strategy'])
        print(strategy)
        print(vault.api_version)
        delegated_assets = strategy.delegatedAssets(block_identifier=report.block_number - 1)
        management_fee = (
            (
                (vault_strategies['totalDebt'] - delegated_assets)
                * duration
                * vault.vault.managementFee(block_identifier=report.block_number - 1)
            )
            / MAX_BPS
            / SECS_PER_YEAR
        )
        strategist_fee = report['gain'] * vault_strategies['performanceFee'] / MAX_BPS
        # NOTE: Unlikely to throw unless strategy reports >1e72 harvest profit
        performance_fee = (
            report['gain'] * vault.vault.performanceFee(block_identifier=report.block_number - 1) / MAX_BPS
        )

        print(management_fee / 1e18, strategist_fee / 1e18, performance_fee / 1e18, sep='\n')
        pps = vault.vault.pricePerShare(block_identifier=report.block_number - 1) / 1e18
        check = logs_by_tx[report.transaction_hash]
        print(
            f'* protocol {(management_fee + performance_fee) / 1e18 / pps} got {check[1]["value"] / 1e18}',
            f'* strateg  {(strategist_fee) / 1e18 / pps} got {check[0]["value"] / 1e18}',
            sep='\n',
        )
        continue
        sender, receiver, amount = log.values()
        if amount == 0:
            return None
        price = magic.get_price(str(vault.vault), log.block_number)
        if receiver in rewards:
            pps = vault.vault.pricePerShare(block_identifier=log.block_number) / vault.scale
            # TODO optimize using events
            perf = vault.vault.performanceFee(block_identifier=log.block_number) / 10_000
            # gain is in vault token, while fee is in vault shares
            gain = gains[log.transaction_hash]
            perf_fee = gain * perf / pps  # wei
            mgmt_fee = amount - perf_fee  # wei

            log_fees = [
                ('performance', perf_fee),
                ('management', mgmt_fee),
            ]
        elif receiver in strategies:
            log_fees = [
                ('strategist', amount),
            ]
        else:
            raise ValueError('unknown fee type')

        for dest, fee in log_fees:
            fees.append(
                {
                    'block_number': log.block_number,
                    'timestamp': get_block_timestamp(log.block_number),
                    'transaction_hash': log.transaction_hash.hex(),
                    'vault': str(vault.vault),
                    'token': str(vault.vault),
                    'strategy': sender,
                    'recipient': receiver,
                    'fee_type': 'harvest',
                    'fee_dest': dest,
                    'token_price': price,
                    'amount_native': fee / vault.scale,
                    'amount_usd': price * fee / vault.scale,
                }
            )
        progress.set_postfix({'total': int(sum(x['amount_usd'] for x in fees))})

    return fees


def v2():
    registry = Registry()
    fees = []
    vaults = [x for x in registry.vaults if Version(x.api_version) < Version('0.3.5')]
    # vaults = registry.vaults
    width = os.get_terminal_size().columns - 1
    for vault in vaults:
        print('-' * width)
        print(vault)
        print('-' * width)
        get_protocol_fees(vault)
    # fees = list(concat(ThreadPoolExecutor().map(get_protocol_fees, vaults)))

    # path = Path('research/traces/07-fees-v2.json')
    # json.dump(fees, path.open('wt'), indent=2)
