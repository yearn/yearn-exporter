import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Tuple, Union

import pandas as pd
from brownie import Contract, chain, convert, multicall, web3
from joblib.parallel import Parallel, delayed
from pandas import DataFrame
from pandas.core.tools.datetimes import DatetimeScalar
from pony.orm import OperationalError, db_session
from rich import print
from rich.progress import track
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import batch_call
from yearn.networks import Network
from yearn.partners.charts import make_partner_charts
from yearn.partners.constants import OPEX_COST, get_tier
from yearn.prices import magic
from yearn.utils import contract, contract_creation_block, get_block_timestamp
from yearn.v2.registry import Registry
from yearn.v2.vaults import Vault

try:
    from yearn.entities import PartnerHarvestEvent
    from yearn.outputs.postgres.utils import cache_address
    USE_POSTGRES_CACHE = True
except OperationalError as e:
    if "Is the server running on that host and accepting TCP/IP connections?" in str(e):
        USE_POSTGRES_CACHE = False
    else:
        raise

logger = logging.getLogger(__name__)


def get_timestamps(blocks: Tuple[int,...]) -> DatetimeScalar:
    data = Parallel(10, 'threading')(
        delayed(get_block_timestamp)(block) for block in blocks
    )
    return pd.to_datetime([x * 1e9 for x in data])


def get_protocol_fees(address: str, start_block: int = None) -> Dict[int,Decimal]:
    """
    Get all protocol fee payouts for a given vault.

    Fees can be found as vault share transfers to the rewards address.
    """
    vault = Vault.from_address(address)
    rewards = vault.vault.rewards()

    topics = construct_event_topic_set(
        filter_by_name('Transfer', vault.vault.abi)[0],
        web3.codec,
        {'sender': address, 'receiver': rewards},
    )
    logs = decode_logs(get_logs_asap(address, topics, from_block=start_block))
    return {log.block_number: Decimal(log['value']) / Decimal(vault.scale) for log in logs}


@dataclass
class Wrapper:
    def __init__(self, name: str, vault: str, wrapper: str) -> None:
        self.name = name
        self.vault = convert.to_address(vault)
        self.wrapper = convert.to_address(wrapper)
    
    @db_session
    def read_cache(self) -> DataFrame:
        entities = PartnerHarvestEvent.select(lambda e: e.vault == self.vault and e.wrapper.address == self.wrapper and e.wrapper.chainid == chain.id)[:]
        cache = [
            {
                'block': e.block,
                'timestamp': pd.to_datetime(e.timestamp,unit='s'),
                'balance': e.balance,
                'total_supply': e.total_supply,
                'vault_price': e.vault_price,
                'balance_usd': e.balance_usd,
                'share': e.share,
                'payout_base': e.payout_base,
                'protocol_fee': e.protocol_fee,
                'wrapper': e.wrapper.address,
                'vault': e.vault,
            } for e in entities
        ]
        return DataFrame(cache)

    def protocol_fees(self, start_block: int = None) -> Dict[int,Decimal]:
        return get_protocol_fees(self.vault, start_block=start_block)

    def balances(self, blocks: Tuple[int,...]) -> List[Decimal]:
        vault = Vault.from_address(self.vault)
        balances = batch_call(
            [[vault.vault, 'balanceOf', self.wrapper, block] for block in blocks]
        )
        return [Decimal(balance) / Decimal(vault.scale) for balance in balances]

    def total_supplies(self, blocks: Tuple[int,...]) -> List[Decimal]:
        vault = Vault.from_address(self.vault)
        supplies = batch_call([[vault.vault, 'totalSupply', block] for block in blocks])
        return [Decimal(supply) / Decimal(vault.scale) for supply in supplies]

    def vault_prices(self, blocks: Tuple[int,...]) -> List[Decimal]:
        prices = Parallel(10, 'threading')(
            delayed(magic.get_price)(self.vault, block=block) for block in blocks
        )
        return [Decimal(price) for price in prices]


class BentoboxWrapper(Wrapper):
    """
    Use BentoBox deposits by wrapper.
    """

    def balances(self, blocks) -> List[Decimal]:
        bentobox = contract('0xF5BCE5077908a1b7370B9ae04AdC565EBd643966')
        vault = Vault.from_address(self.vault)
        balances = batch_call(
            [
                [bentobox, 'balanceOf', self.vault, self.wrapper, block]
                for block in blocks
            ]
        )
        return [Decimal(balance or 0) / Decimal(vault.scale) for balance in balances]

class DegenboxWrapper(Wrapper):
    """
    Use DegenBox deposits by wrapper.
    """

    def balances(self, blocks) -> List[Decimal]:
        degenbox = contract('0xd96f48665a1410C0cd669A88898ecA36B9Fc2cce')
        vault = Vault.from_address(self.vault)
        balances = batch_call(
            [
                [degenbox, 'balanceOf', self.vault, self.wrapper, block]
                for block in blocks
            ]
        )
        return [Decimal(balance or 0) / Decimal(vault.scale) for balance in balances]

class ElementWrapper(Wrapper):
    """
    Use Element deposits by wrapper
    """

    name: str
    wrapper: str

    def unwrap(self) -> List[Wrapper]:
        registry = contract(self.wrapper)
        wrappers = registry.functions.viewRegistry().call()

        return [
            Wrapper(name=contract(wrapper).name(), vault=contract(wrapper).vault(), wrapper=wrapper)
            for wrapper in wrappers
        ]

@dataclass
class WildcardWrapper:
    """
    Automatically find and generate all valid (wrapper, vault) pairs.
    """

    name: str
    wrapper: Union[str, List[str]]  # can unpack multiple wrappers

    def unwrap(self) -> List[Wrapper]:
        registry = Registry()
        wrappers = [self.wrapper] if isinstance(self.wrapper, str) else self.wrapper
        topics = construct_event_topic_set(
            filter_by_name('Transfer', registry.vaults[0].vault.abi)[0],
            web3.codec,
            {'receiver': wrappers},
        )
        addresses = [str(vault.vault) for vault in registry.vaults]
        from_block = min(ThreadPoolExecutor().map(contract_creation_block, addresses))

        # wrapper -> {vaults}
        deposits = defaultdict(set)
        for log in decode_logs(get_logs_asap(addresses, topics, from_block)):
            deposits[log['receiver']].add(log.address)

        return [
            Wrapper(name=vault.name, vault=str(vault.vault), wrapper=wrapper)
            for wrapper in wrappers
            for vault in registry.vaults
            if str(vault.vault) in deposits[wrapper]
        ]


@dataclass
class YApeSwapFactoryWrapper(WildcardWrapper):
    name: str
    wrapper: str

    def unwrap(self) -> List[Wrapper]:
        factory = contract(self.wrapper)
        with multicall:
            pairs = [factory.allPairs(i) for i in range(factory.allPairsLength())]
            ratios = [Contract(pair).farmingRatio() for pair in pairs]

        # pools with ratio.min > 0 deploy to yearn vaults
        farming = [str(pair) for pair, ratio in zip(pairs, ratios) if ratio['min'] > 0]

        return WildcardWrapper(self.name, farming).unwrap()


class GearboxWrapper(Wrapper):
    """
    Use Gearbox CAs as wrappers.
    """

    def balances(self, blocks) -> List[Decimal]:
        GearboxAccountFactory = contract(self.wrapper)
        vault = Vault.from_address(self.vault)

        with multicall:
            CAs = [GearboxAccountFactory.creditAccounts(i) for i in range(GearboxAccountFactory.countCreditAccounts())]
        
        balances = []
        for block in blocks:       
            balances_at_block = batch_call(
                [
                    [
                        vault.vault,
                        'balanceOf',
                        ca,
                        block
                    ]
                    for ca in CAs
                ]
            )   
            tvl = sum(balance / Decimal(vault.scale) for balance in balances_at_block)
            balances.append(tvl)
        return balances

    
@dataclass
class Partner:
    name: str
    wrappers: List[Wrapper]
    treasury: str = None

    @cached_property
    def flat_wrappers(self) -> List[Wrapper]:
        # unwrap wildcard wrappers to a flat list
        flat_wrappers = []
        for wrapper in self.wrappers:
            if isinstance(wrapper, Wrapper):
                flat_wrappers.append(wrapper)
            elif isinstance(wrapper, WildcardWrapper):
                flat_wrappers.extend(wrapper.unwrap())
        return flat_wrappers

    def process(self, use_postgres_cache: bool = USE_POSTGRES_CACHE) -> Tuple[DataFrame,DataFrame]:
        # snapshot wrapper share at each harvest
        wrappers = []
        for wrapper in track(self.flat_wrappers, self.name):
            if use_postgres_cache: 
                cache = wrapper.read_cache()
                try:
                    max_cached_block = int(cache['block'].max())
                    start_block = max_cached_block + 1
                    logger.debug(f'{self.name} {wrapper.name} is cached thru block {max_cached_block}')
                except KeyError:
                    start_block = None
                    logger.debug(f'no harvests cached for {self.name} {wrapper.name}')
                logger.debug(f'start block: {start_block}')
            else:
                start_block = None
            
            protocol_fees = wrapper.protocol_fees(start_block=start_block)
            
            try:
                blocks, protocol_fees = zip(*protocol_fees.items())
                wrap = DataFrame(
                    {
                        'block': blocks,
                        'timestamp': get_timestamps(blocks),
                        'protocol_fee': protocol_fees,
                        'balance': wrapper.balances(blocks),
                        'total_supply': wrapper.total_supplies(blocks),
                        'vault_price': wrapper.vault_prices(blocks),
                    }
                )
                wrap['balance_usd'] = wrap.balance * wrap.vault_price
                wrap['share'] = wrap.balance / wrap.total_supply
                wrap['payout_base'] = wrap.share * wrap.protocol_fee * Decimal(1 - OPEX_COST)
                wrap['protocol_fee'] = wrap.protocol_fee
                wrap['wrapper'] = wrapper.wrapper
                wrap['vault'] = wrapper.vault
            except ValueError as e:
                if str(e) != 'not enough values to unpack (expected 2, got 0)':
                    raise
                wrap = DataFrame()

            if use_postgres_cache:
                cache_data(wrap)
                wrap = pd.concat([wrap,cache])
            
            try:
                wrap = wrap.set_index('block')
            except KeyError:
                logger.info('no fees for %s', wrapper.name)
                continue

            # TODO: save a csv for reporting
            wrappers.append(wrap)

        # if nothing to report, move to next partner
        if len(wrappers) == 0:
            return DataFrame(), DataFrame()

        # calculate partner fee tier from cummulative wrapper balances
        partner = pd.concat(wrappers)
        total_balances = (
            pd.pivot_table(partner, 'balance_usd', 'block', 'vault', 'sum')
            .ffill()
            .sum(axis=1)
        )
        tiers = total_balances.apply(get_tier).rename('tier')

        # calculate final payout by vault after tier adjustments
        partner = partner.join(tiers)
        partner['payout'] = partner.payout_base * partner.tier
        partner['payout_usd'] = partner.payout * partner.vault_price
        partner['protocol_fee_usd'] = partner.protocol_fee * partner.vault_price

        self.export_csv(partner)
        payouts = self.export_payouts(partner)

        if partner.payout.sum():
            make_partner_charts(self, partner)

        return partner, payouts

    def export_csv(self, partner: DataFrame) -> None:
        path = Path(f'research/partners/{self.name}/partner.csv')
        path.parent.mkdir(parents=True, exist_ok=True)
        partner.to_csv(path)

    def export_payouts(self, partner: DataFrame) -> DataFrame:
        # calculate payouts grouped by month and vault token
        payouts = (
            pd.pivot_table(
                partner,
                ['payout', 'payout_usd', 'protocol_fee', 'protocol_fee_usd'],
                'timestamp',
                'vault',
                'sum',
            )
            .resample('1M')
            .sum()
        )
        # stack from wide to long format with one payment per line
        payouts = payouts.stack().reset_index()
        payouts['treasury'] = self.treasury
        payouts['partner'] = self.name
        # reorder columns
        payouts.columns = [
            'timestamp',
            'token',
            'amount',
            'amount_usd',
            'protocol_fee',
            'protocol_fee_usd',
            'treasury',
            'partner',
        ]
        payouts = payouts[
            [
                'timestamp',
                'partner',
                'token',
                'treasury',
                'amount',
                'amount_usd',
                'protocol_fee',
                'protocol_fee_usd',
            ]
        ]
        payouts.to_csv(Path(f'research/partners/{self.name}/payouts.csv'), index=False)
        return payouts


def process_partners(partners: List[Partner], use_postgres_cache: bool = USE_POSTGRES_CACHE) -> DataFrame:
    if not partners:
        raise UnsupportedNetwork(f'There are no partners on {Network.label()}')

    total = 0
    payouts = []
    if not use_postgres_cache:
        logger.warn('This script can run much faster for subsequent runs if you cache the data to postgres.')
        logger.warn("Caching will be enabled by default if you run the yearn-exporter locally.")
        logger.warn('To enable caching without running the exporter, run `make postgres` from project root.')
    for partner in partners:
        result, payout = partner.process(use_postgres_cache=use_postgres_cache)
        if len(result) == len(payout) == 0:
            continue
        payouts.append(payout)
        usd = (result.payout * result.vault_price).sum()
        print(partner.name, round(usd,2), 'usd to pay')
        total += usd

    print(round(total,2), 'total so far')
    path = Path('research/partners/payouts.csv')
    df = pd.concat(payouts).sort_values(['timestamp','partner','token']).fillna(0)
    df.to_csv(path, index=False)
    print(f'saved to {path}')

    # show summary by month and partner
    print(df.groupby('timestamp').sum().amount_usd)

    summary = df.groupby(['timestamp', 'partner']).sum().amount_usd.unstack()
    print(summary.iloc[-9:].T)  # last 9 months
    return df

@db_session
def cache_data(wrap: DataFrame) -> None:
    '''
    saves rows into postgres for faster execution on future runs
    '''
    for i, row in wrap.iterrows():
        PartnerHarvestEvent(
            block=row.block,
            timestamp=int(row.timestamp.timestamp()),
            balance=row.balance,
            total_supply=row.total_supply,
            vault_price=row.vault_price,
            balance_usd=row.balance_usd,
            share=row.share,
            payout_base=row.payout_base,
            protocol_fee=row.protocol_fee,
            wrapper=cache_address(row.wrapper),
            vault=row.vault,
        )
