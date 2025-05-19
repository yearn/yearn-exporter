import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from typing import (AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple,
                    Union)

import a_sync
import pandas as pd
from a_sync import igather
from async_lru import alru_cache
from async_property import async_cached_property
from brownie import convert, chain, web3
from dank_mids.helpers import lru_cache_lite
from pandas import DataFrame
from pandas.core.tools.datetimes import DatetimeScalar
from pony.orm import OperationalError, commit, db_session
from rich import print
from tqdm.asyncio import tqdm_asyncio
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y import Contract, ERC20, Network, contract_creation_block_async, get_price
from y.constants import CHAINID
from y.exceptions import continue_if_call_reverted
from y.time import get_block_timestamp_async, last_block_on_date
from y.utils.events import BATCH_SIZE, Events

from yearn.constants import ERC20_TRANSFER_EVENT_HASH
from yearn.events import decode_logs
from yearn.exceptions import UnsupportedNetwork
from yearn.partners.charts import make_partner_charts
from yearn.partners.constants import OPEX_COST, get_tier
from yearn.partners.delegated import delegated_deposit_balances
from yearn.typing import Address, Block
from yearn.v2.registry import Registry
from yearn.v2.vaults import Vault

try:
    from yearn.entities import PartnerHarvestEvent
    from yearn.outputs.postgres.utils import (address_dbid, chain_dbid,
                                              token_dbid)
    USE_POSTGRES_CACHE = True
except OperationalError as e:
    if "Is the server running on that host and accepting TCP/IP connections?" in str(e):
        USE_POSTGRES_CACHE = False
    else:
        raise

logger = logging.getLogger(__name__)

threads = a_sync.AsyncThreadPoolExecutor(8)

async def get_timestamps(blocks: Tuple[int,...]) -> DatetimeScalar:
    data = await asyncio.gather(*[get_block_timestamp_async(block) for block in blocks])
    return pd.to_datetime([x * 1e9 for x in data])


@dataclass(frozen=True)
class Wrapper:
    def __init__(self, name: str, vault: str, wrapper: str) -> None:
        # Format attributes
        attrs = {
            'name': name,
            'vault': convert.to_address(vault),
            'wrapper': convert.to_address(wrapper),
            # NOTE: We need to use a queue here to ensure at most one active coroutine is populating the db for this wrapper
            'get_data': a_sync.ProcessingQueue(self._get_data, 1),
        }
        # Set attributes using super() to avoid FrozenInstanceError
        for k, v in attrs.items():
            super().__setattr__(k, v)
    
    @cached_property
    def _vault(self) -> Vault:
        return Vault.from_address(self.vault)
    
    @property
    def vault_contract(self) -> Contract:
        return self._vault.vault
    
    @property
    def scale(self) -> int:
        return self._vault.scale
    
    async def _get_data(self, partner: "Partner", use_postgres_cache: bool, verbose: bool = False) -> DataFrame:
        if verbose:
            logger.info(f'starting {partner.name} {self} {self.name} {self.wrapper} for {self.vault}')
        if use_postgres_cache:
            cache = await threads.run(self.read_cache)
            try:
                max_cached_block = int(cache['block'].max())
                logger.debug('%s %s is cached thru block %s', partner.name, self.name, max_cached_block)
                start_block = max_cached_block + 1 if partner.start_block is None else max(partner.start_block, max_cached_block + 1)
            except KeyError:
                start_block = partner.start_block
                logger.debug('no harvests cached for %s %s', partner.name, self.name)
            logger.debug('start block: %s', start_block)
        else:
            start_block = partner.start_block
        
        futs = []
        async for block, fee in self.protocol_fees(start_block=start_block):
            futs.append(asyncio.create_task(process_harvests(self, block, fee)))
        data = [data for data in await asyncio.gather(*futs) if data is not None]
        data = pd.concat(data) if data else DataFrame()
        
        if use_postgres_cache:
            await threads.run(cache_data, data)
            data = pd.concat([cache, data])
        
        return data
    
    @db_session
    def read_cache(self) -> DataFrame:
        entities = PartnerHarvestEvent.select(lambda e: e.vault.address.address == self.vault and e.wrapper.address == self.wrapper and e.chain.chainid == CHAINID)[:]
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

    async def protocol_fees(self, start_block: int = None) -> AsyncGenerator[Dict[Block, Decimal], None]:
        """
        Get all protocol fee payouts for a given vault.

        Fees can be found as vault share transfers to the rewards address.
        """
        vault = Vault.from_address(self.vault)
        rewards = await vault.vault.rewards.coroutine()
        topics = construct_event_topic_set(
            filter_by_name('Transfer', vault.vault.abi)[0],
            web3.codec,
            {'sender': self.vault, 'receiver': rewards},
        )
        try:
            wrapper_deploy_block = await contract_creation_block_async(self.wrapper)
            should_include = lambda log: log.block_number >= wrapper_deploy_block and (start_block is None or log.block_number >= start_block)
            
            # Do some funky stuff here so we can make use of the disk cache
            logs_start_block = await contract_creation_block_async(self.vault)
            while logs_start_block + BATCH_SIZE <= wrapper_deploy_block:
                logs_start_block += BATCH_SIZE
                
        except ValueError as e:
            if not str(e).startswith("Unable to find deploy block for "):
                raise e
            should_include = lambda log: start_block is None or log.block_number >= start_block
        
            # Do some funky stuff here so we can make use of the disk cache
            logs_start_block = await contract_creation_block_async(self.vault)
            while start_block and logs_start_block + BATCH_SIZE <= start_block:
                logs_start_block += BATCH_SIZE
        
        async for event in Events(addresses=self.vault, topics=topics, from_block=logs_start_block).events(chain.height):
            if should_include(event):
                yield {event.block_number: Decimal(event['value']) / vault.scale}

    async def balances(self, blocks: Tuple[int,...]) -> List[Decimal]:
        balanceOf = self.vault_contract.balanceOf.coroutine
        balances = await igather(balanceOf(self.wrapper, block_identifier=block) for block in blocks)
        scale = self.scale
        return [Decimal(balance) / scale for balance in balances]

    async def total_supplies(self, blocks: Tuple[int,...]) -> List[Decimal]:
        total_supply_cached = _get_cached_total_supply_fn(self.vault_contract)
        supplies = await igather(total_supply_cached(block_identifier = block) for block in blocks)
        scale = self.scale
        return [Decimal(supply) / scale for supply in supplies]

    async def vault_prices(self, blocks: Tuple[int,...]) -> List[Decimal]:
        return [Decimal(price) for price in await asyncio.gather(*[get_price(self.vault, block=block, sync=False) for block in blocks])]


class BentoboxWrapper(Wrapper):
    """
    Use BentoBox deposits by wrapper.
    """
    @async_cached_property
    async def bentobox(self) -> Contract:
        if CHAINID in [Network.Mainnet, Network.Fantom]:
            return await Contract.coroutine("0xF5BCE5077908a1b7370B9ae04AdC565EBd643966")
        raise UnsupportedNetwork()

    async def balances(self, blocks) -> List[Decimal]:
        balances = await asyncio.gather(*[self.get_balance(block) for block in blocks])
        return [Decimal(balance or 0) / self.scale for balance in balances]
    
    async def get_balance(self, block) -> Optional[int]:
        bento = await self.bentobox
        try:
            return await bento.balanceOf.coroutine(self.vault, self.wrapper, block_identifier=block)
        except Exception as e:
            continue_if_call_reverted(e)


class DegenboxWrapper(Wrapper):
    """
    Use DegenBox deposits by wrapper.
    """
    @async_cached_property
    async def degenbox(self) -> Contract:
        if CHAINID == Network.Mainnet:
            return await Contract.coroutine("0xd96f48665a1410C0cd669A88898ecA36B9Fc2cce")
        raise UnsupportedNetwork()

    async def balances(self, blocks) -> List[Decimal]:
        balances = await asyncio.gather(*[self.get_balance(block) for block in blocks])
        return [Decimal(balance or 0) / self.scale for balance in balances]
    
    async def get_balance(self, block) -> Optional[int]:
        degenbox = await self.degenbox
        try:
            return await degenbox.balanceOf.coroutine(self.vault, self.wrapper, block_identifier=block)
        except Exception as e:
            continue_if_call_reverted(e)


@dataclass(frozen=True)
class WildcardWrapper:
    """
    Automatically find and generate all valid (wrapper, vault) pairs.
    """

    name: str
    wrapper: Union[str, List[str]]  # can unpack multiple wrappers

    def __post_init__(self):
        # If multiple wrappers, ensure tuple for hashability
        if not isinstance(self.wrapper, str):
            super().__setattr__('wrapper', tuple(self.wrapper))

    async def unwrap(self) -> List[Wrapper]:
        registry = Registry()
        wrappers = [self.wrapper] if isinstance(self.wrapper, str) else self.wrapper
        vaults = await registry.vaults
        topics = construct_event_topic_set(
            filter_by_name('Transfer', vaults[0].vault.abi)[0],
            web3.codec,
            {'receiver': wrappers},
        )
        addresses = [str(vault.vault) for vault in vaults]
        from_block = min(await asyncio.gather(*[contract_creation_block_async(address) for address in addresses]))

        # wrapper -> {vaults}
        deposits = defaultdict(set)
        async for event in Events(addresses=addresses, topics=topics, from_block=from_block).events(chain.height):
            deposits[event['receiver']].add(event.address)

        return [
            Wrapper(name=vault.name, vault=str(vault.vault), wrapper=wrapper)
            for wrapper in wrappers
            for vault in vaults
            if str(vault.vault) in deposits[wrapper]
        ]


class ElementWrapper(WildcardWrapper):
    """
    Use Element deposits by wrapper
    """

    name: str
    wrapper: str

    async def unwrap(self) -> List[Wrapper]:
        registry = await Contract.coroutine(self.wrapper)
        wrappers = await asyncio.gather(*[Contract.coroutine(wrapper) for wrapper in await registry.viewRegistry.coroutine()])
        info = await asyncio.gather(*[asyncio.gather(ERC20(wrapper, asynchronous=True).name, wrapper.vault.coroutine()) for wrapper in wrappers])
        return [Wrapper(name=name, vault=vault, wrapper=wrapper) for wrapper, (name, vault) in zip(wrappers, info)]


class YApeSwapFactoryWrapper(WildcardWrapper):
    name: str
    wrapper: str

    async def unwrap(self) -> List[Wrapper]:
        factory = await Contract.coroutine(self.wrapper)
        pairs: List[Address] = await igather(map(factory.allPairs.coroutine, range(await factory.allPairsLength)))
        pair_contracts: List[Contract] = await igather(map(Contract.coroutine, pairs))
        ratios: List[int] = await igather(pair.farmingRatio for pair in pair_contracts)
        # pools with ratio.min > 0 deploy to yearn vaults
        farming = [pair.address for pair, ratio in zip(pair_contracts, ratios) if ratio['min'] > 0]
        return await WildcardWrapper(self.name, farming).unwrap()


class GearboxWrapper(Wrapper):
    """
    Use Gearbox CAs as wrappers.
    """
    def __post_init__(self):
        self.get_balance = a_sync.ProcessingQueue(self._get_balance, 5000)

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
        return await asyncio.gather(*[self.get_tvl(block) for block in blocks])
    
    async def get_tvl(self, block: int) -> Decimal:
        if ct := await self.count_credit_accounts(block):
            credit_accounts, depositors = await asyncio.gather(
                asyncio.gather(*[self.get_credit_account(i) for i in range(ct)]),
                self.get_vault_depositors(block),
            )
            return sum(await asyncio.gather(*[self.get_balance(ca, block) for ca in credit_accounts if ca in depositors]))
        return Decimal(0)
    
    async def count_credit_accounts(self, block: int) -> int:
        factory = await self.account_factory
        try:
            return await factory.countCreditAccounts.coroutine(block_identifier=block)
        except Exception as e:
            continue_if_call_reverted(e)
    
    @async_cached_property
    async def _transfers_container(self) -> Events:
        from_block = await contract_creation_block_async(self.wrapper)
        return Events(addresses=self.vault, topics=[ERC20_TRANSFER_EVENT_HASH], from_block=from_block)

    async def _get_balance(self, credit_account: Address, block: int) -> Decimal:
        return Decimal(await self.vault_contract.balanceOf.coroutine(credit_account, block_identifier=block)) / self.scale
    
    async def get_vault_depositors(self, block: int) -> Set[Address]:
        transfers = await self._transfers_container
        return {transfer['receiver'] async for transfer in transfers.events(to_block=block)}
        
        
class InverseWrapper(Wrapper):
    def __post_init__(self):
        self.get_balance = a_sync.ProcessingQueue(self._get_balance, num_workers=5000)

    def __hash__(self) -> int:
        return hash(self.vault + self.wrapper)
    
    async def balances(self, blocks) -> List[Decimal]:
        return await asyncio.gather(*[self.get_tvl(block) for block in blocks])
    
    async def get_tvl(self, block: int) -> Decimal:
        # We use futs instead of gather here so we can process logs as they come in vs waiting for all of them before proceeding
        futs = [self.get_balance(escrow, block) async for escrow in self.get_escrows(block)]
        return sum(await asyncio.gather(*futs))
    
    async def _get_balance(self, escrow: Address, block: int) -> Decimal:
        escrow = await Contract.coroutine(escrow)
        return Decimal(await escrow.balance.coroutine(block_identifier=block)) / self.scale
    
    async def get_escrows(self, block) -> AsyncGenerator[Address, None]:
        wrapper_contract = await Contract.coroutine(self.wrapper)
        async for event in wrapper_contract.events.CreateEscrow.events(to_block=block):
            yield event['escrow']
    

class DelegatedDepositWrapper(Wrapper):
    """
    Set `wrapper` equal to the the partner's partnerId from the YearnPartnerTracker contract.
    """

    async def balances(self, blocks: List[Block]) -> List[Decimal]:
        return await asyncio.gather(*[self.get_balance_at_block(block) for block in blocks])
            
    async def get_balance_at_block(self, block: Block) -> Decimal:
        balances = await delegated_deposit_balances()
        vault_balances = balances[self.vault]
        wrapper = self.wrapper
        total = sum(
            asofdict[block]
            for depositor in vault_balances
            for partnerId, asofdict in vault_balances[depositor].items()
            if partnerId == wrapper
        )
        return Decimal(total) / self.scale
        

@dataclass
class DelegatedDepositWildcardWrapper:
    """
    Automatically find and generate all valid (partnerId, vault) pairs using a valid delegated deposit partnerId.
    """

    name: str
    partnerId: str

    async def unwrap(self) -> List[Wrapper]:
        wrappers = []
        for vault in await delegated_deposit_balances():
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

@dataclass(frozen=True)
class Partner:
    name: str
    start_date: Optional[date]
    wrappers: Tuple[Wrapper]
    treasury: str = None
    retired_treasuries: Tuple[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Format attributes consistently
        name = self.name.lower()
        attrs = {'name': name}
        if self.start_date is None and name in NO_START_DATE:
            attrs['start_block'] = None
        elif self.start_date is None:
            raise ValueError("You must provide a `start_date`.")
        elif isinstance(self.start_date, date):
            attrs['start_block'] = last_block_on_date(self.start_date - timedelta(days=1)) + 1
        else:
            raise TypeError("`start_date` must be a `datetime.date` object.")
        # Ensure tuple for hashability
        attrs['wrappers'] = tuple(self.wrappers)
        # Checksum addresses
        if self.treasury:
            attrs['treasury'] = convert.to_address(self.treasury)
        if self.retired_treasuries:
            attrs['retired_treasuries'] = tuple(convert.to_address(addr) for addr in self.retired_treasuries)
        # Set attributes using super() to avoid FrozenInstanceError
        for k, v in attrs.items():
            super().__setattr__(k, v)
            

    @async_cached_property
    async def flat_wrappers(self) -> List[Wrapper]:
        # unwrap wildcard wrappers to a flat list
        flat_wrappers = []
        for wrapper in self.wrappers:
            logger.info("loading %s wrapper %s", self, wrapper)
            if isinstance(wrapper, Wrapper):
                flat_wrappers.append(wrapper)
                logger.info("loaded %s wrapper %s", self, wrapper)
            elif isinstance(wrapper, (WildcardWrapper, DelegatedDepositWildcardWrapper)):
                flat_wrappers.extend(await wrapper.unwrap())
                logger.info("loaded %s wrapper %s", self, wrapper)
        return flat_wrappers

    async def process(self, use_postgres_cache: bool = USE_POSTGRES_CACHE, verbose: bool = False) -> Tuple[DataFrame,DataFrame]:
        # TODO Optimize this a bit better.
        # snapshot wrapper share at each harvest
        wrappers = []
        gather = tqdm_asyncio.gather if verbose else asyncio.gather
        data = await gather(*[wrapper.get_data(self, use_postgres_cache, verbose=verbose) for wrapper in await self.flat_wrappers])
        for wrapper, data in zip(await self.flat_wrappers, data):
            try:
                data = data.set_index('block')
            except KeyError:
                if verbose:
                    logger.info('no fees for %s', wrapper.name)
                continue

            # TODO: save a csv for reporting
            wrappers.append(data)

        # if nothing to report, move to next partner
        if not wrappers:
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
        # NOTE: This must be done in order to ensure data integrity

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

def process_partners(partners: List[Partner], use_postgres_cache: bool = USE_POSTGRES_CACHE, verbose: bool = False) -> DataFrame:
    if not partners:
        raise UnsupportedNetwork(f'There are no partners on {Network.label()}')

    total = 0
    payouts = []
    if not use_postgres_cache:
        logger.warning('This script can run much faster for subsequent runs if you cache the data to postgres.')
        logger.warning("Caching will be enabled by default if you run the yearn-exporter locally.")
        logger.warning('To enable caching without running the exporter, run `make postgres` from project root.')

    partners_data: List[Tuple[DataFrame, DataFrame]] = asyncio.get_event_loop().run_until_complete(
        tqdm_asyncio.gather(*[partner.process(use_postgres_cache=use_postgres_cache, verbose=verbose) for partner in partners])
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
            chain=chain_dbid(),
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
            wrapper=address_dbid(row.wrapper),
            vault=token_dbid(row.vault),
        )
        commit()

async def process_harvests(wrapper, block, fee) -> Optional[DataFrame]:
    # legacy uglyness to avoid refactoring code below
    blocks = [block]
    protocol_fees = [fee]

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
    return wrap

@lru_cache_lite
def _get_cached_total_supply_fn(vault: Contract) -> Callable[[], int]:
    return alru_cache(maxsize=None)(vault.totalSupply.coroutine)