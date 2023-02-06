import asyncio
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from typing import Dict, List, Tuple, Union
from async_property import async_cached_property

import pandas as pd
from async_lru import alru_cache
from brownie import chain, convert, multicall, web3
from pandas import DataFrame
from pandas.core.tools.datetimes import DatetimeScalar
from pony.orm import OperationalError, commit, db_session
from rich import print
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y.time import last_block_on_date
from y import Contract, get_price_async
from y.constants import thread_pool_executor
from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.networks import Network
from yearn.partners.charts import make_partner_charts
from yearn.partners.constants import OPEX_COST, get_tier
from yearn.partners.delegated import DELEGATED_BALANCES
from yearn.typing import Address, Block
from yearn.utils import contract, contract_creation_block, get_block_timestamp, run_in_thread
from yearn.v2.registry import Registry
from yearn.v2.vaults import Vault

try:
    from yearn.entities import PartnerHarvestEvent
    from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                              cache_token)
    USE_POSTGRES_CACHE = True
except OperationalError as e:
    if "Is the server running on that host and accepting TCP/IP connections?" in str(e):
        USE_POSTGRES_CACHE = False
    else:
        raise

logger = logging.getLogger(__name__)


async def get_timestamps(blocks: Tuple[int,...]) -> DatetimeScalar:
    loop = asyncio.get_event_loop()
    data = await asyncio.gather(*[run_in_thread(get_block_timestamp, block) for block in blocks])
    return pd.to_datetime([x * 1e9 for x in data])


def get_protocol_fees(address: str, start_block: Optional[int] = None) -> Dict[int,Decimal]:
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
    
    @cached_property
    def _vault(self) -> Vault:
        return Vault.from_address(self.vault)
    
    @property
    def vault_contract(self) -> Contract:
        return self._vault.vault
    
    @property
    def scale(self) -> int:
        return self._vault.scale
    
    @db_session
    def read_cache(self) -> DataFrame:
        entities = PartnerHarvestEvent.select(lambda e: e.vault.address.address == self.vault and e.wrapper.address == self.wrapper and e.chain.chainid == chain.id)[:]
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
                'vault': e.vault.address.address,
            } for e in entities
        ]
        return DataFrame(cache)

    def protocol_fees(self, start_block: int = None) -> Dict[int,Decimal]:
        return get_protocol_fees(self.vault, start_block=start_block)

    async def balances(self, blocks: Tuple[int,...]) -> List[Decimal]:
        wrapper = self.wrapper
        coro_fn = self.vault_contract.balanceOf.coroutine
        balances = await asyncio.gather(*[coro_fn(wrapper, block_identifier=block) for block in blocks])
        scale = self.scale
        return [Decimal(balance) / Decimal(scale) for balance in balances]

    async def total_supplies(self, blocks: Tuple[int,...]) -> List[Decimal]:
        coro_fn = self.vault_contract.totalSupply.coroutine
        supplies = await asyncio.gather(*[coro_fn(block_identifier = block) for block in blocks])
        scale = self.scale
        return [Decimal(supply) / Decimal(scale) for supply in supplies]

    async def vault_prices(self, blocks: Tuple[int,...]) -> List[Decimal]:
        vault = self.vault
        prices = await asyncio.gather(*[get_price_async(vault, block=block) for block in blocks])
        return [Decimal(price) for price in prices]


class BentoboxWrapper(Wrapper):
    """
    Use BentoBox deposits by wrapper.
    """
    @async_cached_property
    async def bentobox(self) -> Contract:
        if chain.id in [Network.Mainnet, Network.Fantom]:
            return await Contract.coroutine("0xF5BCE5077908a1b7370B9ae04AdC565EBd643966")
        raise UnsupportedNetwork()

    async def balances(self, blocks) -> List[Decimal]:
        bentobox = await self.bentobox
        coro_fn = bentobox.balanceOf.coroutine
        vault = self.vault
        wrapper = self.wrapper
        balances = await asyncio.gather(*[coro_fn(vault, wrapper, block_identifier = block) for block in blocks])
        scale = self.scale
        return [Decimal(balance or 0) / Decimal(scale) for balance in balances]

class DegenboxWrapper(Wrapper):
    """
    Use DegenBox deposits by wrapper.
    """
    @async_cached_property
    async def degenbox(self) -> Contract:
        if chain.id == Network.Mainnet:
            return await Contract.coroutine("0xd96f48665a1410C0cd669A88898ecA36B9Fc2cce")
        raise UnsupportedNetwork()

    async def balances(self, blocks) -> List[Decimal]:
        vault = self.vault
        wrapper = self.wrapper
        degenbox = await self.degenbox
        coro_fn = degenbox.balanceOf.coroutine
        balances = await asyncio.gather(*[coro_fn(vault, wrapper, block_identifier=block) for block in blocks])
        scale = self.scale
        return [Decimal(balance or 0) / Decimal(scale) for balance in balances]


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


class ElementWrapper(WildcardWrapper):
    """
    Use Element deposits by wrapper
    """

    name: str
    wrapper: str

    def unwrap(self) -> List[Wrapper]:
        registry = contract(self.wrapper)
        wrappers = registry.viewRegistry()

        return [
            Wrapper(name=contract(wrapper).name(), vault=contract(wrapper).vault(), wrapper=wrapper)
            for wrapper in wrappers
        ]


@dataclass
class YApeSwapFactoryWrapper(WildcardWrapper):
    name: str
    wrapper: str

    def unwrap(self) -> List[Wrapper]:
        factory = contract(self.wrapper)
        with multicall:
            pairs = [factory.allPairs(i) for i in range(factory.allPairsLength())]
            ratios = [contract(pair).farmingRatio() for pair in pairs]

        # pools with ratio.min > 0 deploy to yearn vaults
        farming = [str(pair) for pair, ratio in zip(pairs, ratios) if ratio['min'] > 0]

        return WildcardWrapper(self.name, farming).unwrap()


class GearboxWrapper(Wrapper):
    """
    Use Gearbox CAs as wrappers.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def __hash__(self) -> int:
        return hash(self.vault + self.wrapper)
    
    @async_cached_property
    async def account_factory(self) -> Contract:
        return await Contract.coroutine(self.wrapper)
    
    @alru_cache(maxsize=None)
    async def get_credit_account(self, ix: int) -> Address:
        factory = await self.account_factory
        return await factory.creditAccounts.coroutine(ix)

    async def balances(self, blocks) -> List[Decimal]:
        factory = await self.account_factory
        coro_fn = factory.countCreditAccounts.coroutine
        count_credit_accounts = await asyncio.gather(*[coro_fn(block_identifier=block) for block in blocks])
        credit_accounts_by_block = await asyncio.gather(*[asyncio.gather(*[self.get_credit_account(i) for i in range(ct)]) for ct in count_credit_accounts])
        return await asyncio.gather(*[self.get_balances_for_block(block, credit_accounts) for block, credit_accounts in zip(blocks, credit_accounts_by_block)])
    
    async def get_balances_for_block(self, block: int, credit_accounts: List[Address]) -> Decimal:
        coro_fn = self.vault_contract.balanceOf.coroutine
        return sum(await asyncio.gather(*[coro_fn(ca, block_identifier=block) for ca in credit_accounts])) / Decimal(self.scale)


class DelegatedDepositWrapper(Wrapper):
    """
    Set `wrapper` equal to the the partner's partnerId from the YearnPartnerTracker contract.
    """

    async def balances(self, blocks: List[Block]) -> List[Decimal]:
        balances = await asyncio.gather(*[self.get_balance_at_block(block) for block in blocks])
        scale = Decimal(self.scale)
        return [balance / scale for balance in balances]
            
    async def get_balance_at_block(self, block: Block) -> Decimal:
        vault_balances = DELEGATED_BALANCES[self.vault]
        wrapper = self.wrapper
        total = sum(
            asofdict[block]
            for depositor in vault_balances
            for partnerId, asofdict in vault_balances[depositor].items()
            if partnerId == wrapper
        )
        return Decimal(total)
        

@dataclass
class DelegatedDepositWildcardWrapper:
    """
    Automatically find and generate all valid (partnerId, vault) pairs using a valid delegated deposit partnerId.
    """

    name: str
    partnerId: str

    def unwrap(self) -> List[Wrapper]:
        wrappers = []
        for vault in DELEGATED_BALANCES:
            vault = Vault.from_address(vault)
            wrappers.append(DelegatedDepositWrapper(name=vault.name, vault=vault.vault.address, wrapper=self.partnerId))
        return wrappers


NO_START_DATE = [
    # NOTE Do not edit this list.
    #   All new partners must define a start_date.
    "abracadabra", "akropolis", "alchemix", "ambire", "badger", "basketdao",
    "beethovenx", "chfry", "cofi", "coinomo", "deus", "donutapp", "element",
    "frax", "gb", "gearbox", "inverse", "", "mover", "pickle", "popcorndao",
    "qidao", "shapeshiftdao", "sturdy", "tempus", "wido", "yapeswap", "yieldster"
]

@dataclass
class Partner:
    name: str
    start_date: date
    wrappers: List[Wrapper]
    treasury: str = None
    retired_treasuries: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Format attributes as desired
        self.name = self.name.lower()
        if self.start_date is None and self.name in NO_START_DATE:
            self.start_block = None
        elif self.start_date is None:
            raise ValueError("You must provide a `start_date`.")
        elif isinstance(self.start_date, date):
            self.start_block = last_block_on_date(self.start_date - timedelta(days=1)) + 1
        else:
            raise TypeError("`start_date` must be a `datetime.date` object.")
            

    @cached_property
    def flat_wrappers(self) -> List[Wrapper]:
        # unwrap wildcard wrappers to a flat list
        flat_wrappers = []
        for wrapper in self.wrappers:
            if isinstance(wrapper, Wrapper):
                flat_wrappers.append(wrapper)
            elif isinstance(wrapper, WildcardWrapper) or isinstance(wrapper, DelegatedDepositWildcardWrapper):
                flat_wrappers.extend(wrapper.unwrap())
        return flat_wrappers

    async def process(self, use_postgres_cache: bool = USE_POSTGRES_CACHE) -> Tuple[DataFrame,DataFrame]:
        # TODO Optimize this a bit better.

        # snapshot wrapper share at each harvest
        wrappers = []
        for wrapper in tqdm(self.flat_wrappers, self.name):
            # NOTE this is all sync code
            # TODO optimize this section
            if use_postgres_cache: 
                cache = wrapper.read_cache()
                try:
                    max_cached_block = int(cache['block'].max())
                    logger.debug(f'{self.name} {wrapper.name} is cached thru block {max_cached_block}')
                    start_block = max_cached_block + 1 if self.start_block is None else max(self.start_block, max_cached_block + 1)
                except KeyError:
                    start_block = self.start_block
                    logger.debug(f'no harvests cached for {self.name} {wrapper.name}')
                logger.debug(f'start block: {start_block}')
            else:
                start_block = self.start_block
            
            protocol_fees = wrapper.protocol_fees(start_block=start_block)
            # NOTE end sync code
            
            try:
                blocks, protocol_fees = zip(*protocol_fees.items())
                timestamps, balances, total_supplys, vault_prices = await asyncio.gather(
                    get_timestamps(blocks),
                    wrapper.balances(blocks),
                    wrapper.total_supplies(blocks),
                    wrapper.vault_prices(blocks),
                )
                wrap = DataFrame(
                    {
                        'block': blocks,
                        'timestamp': timestamps,
                        'protocol_fee': protocol_fees,
                        'balance': balances,
                        'total_supply': total_supplys,
                        'vault_price': vault_prices,
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
        payouts.to_csv(Path(f'research/partners/{self.name}/payouts_{Network.label()}.csv'), index=False)
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

    partners_data: List[Tuple[DataFrame, DataFrame]] = asyncio.get_event_loop().run_until_complete(
        asyncio.gather(*[partner.process(use_postgres_cache=use_postgres_cache) for partner in partners])
    )
    for partner, (result, payout) in zip(partners, partners_data):
        if len(result) == len(payout) == 0:
            continue
        payouts.append(payout)
        usd = (result.payout * result.vault_price).sum()
        print(partner.name, round(usd,2), 'usd to pay')
        total += usd

    print(round(total,2), 'total so far')
    path = Path(f'research/partners/payouts_{Network.label()}.csv')
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
            chain=cache_chain(),
            block=row.block,
            timestamp=int(row.timestamp.timestamp()),
            balance=row.balance,
            total_supply=row.total_supply,
            vault_price=row.vault_price,
            balance_usd=row.balance_usd,
            share=row.share,
            payout_base=row.payout_base,
            protocol_fee=row.protocol_fee,
            # Use cache_address instead of cache_token because some wrappers aren't verified
            wrapper=cache_address(row.wrapper),
            vault=cache_token(row.vault),
        )
        commit()
