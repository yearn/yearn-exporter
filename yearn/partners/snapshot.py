import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property, lru_cache
from pathlib import Path
from typing import (AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple,
                    Union)

import pandas as pd
from a_sync import AsyncThreadPoolExecutor
from async_lru import alru_cache
from async_property import async_cached_property
from brownie import chain, convert, web3
from pandas import DataFrame
from pandas.core.tools.datetimes import DatetimeScalar
from pony.orm import OperationalError, commit, db_session
from rich import print
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y import ERC20, Contract, get_price
from y.contracts import contract_creation_block, contract_creation_block_async
from y.exceptions import continue_if_call_reverted
from y.networks import Network
from y.time import get_block_timestamp_async, last_block_on_date
from y.utils.events import BATCH_SIZE, get_logs_asap_generator

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
    from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                              cache_token)
    USE_POSTGRES_CACHE = True
except OperationalError as e:
    if "Is the server running on that host and accepting TCP/IP connections?" in str(e):
        USE_POSTGRES_CACHE = False
    else:
        raise

logger = logging.getLogger(__name__)

threads = AsyncThreadPoolExecutor(8)

async def get_timestamps(blocks: Tuple[int,...]) -> DatetimeScalar:
    data = await asyncio.gather(*[get_block_timestamp_async(block) for block in blocks])
    return pd.to_datetime([x * 1e9 for x in data])


@dataclass
class Wrapper:
    def __init__(self, name: str, vault: str, wrapper: str) -> None:
        self.name = name
        self.vault = convert.to_address(vault)
        self.wrapper = convert.to_address(wrapper)
        self.semaphore = asyncio.Semaphore(1)
    
    @cached_property
    def _vault(self) -> Vault:
        return Vault.from_address(self.vault)
    
    @property
    def vault_contract(self) -> Contract:
        return self._vault.vault
    
    @property
    def scale(self) -> int:
        return self._vault.scale
    
    async def get_data(self, partner: "Partner", use_postgres_cache: bool) -> DataFrame:
        logger.info(f'starting to process {partner.name} {self} {self.name} {self.vault} {self.wrapper}')
        # NOTE: We need to use a semaphore here to ensure at most one active coroutine is populating the db for this wrapper
        async with self.semaphore:
            if use_postgres_cache: 
                cache = await threads.run(self.read_cache)
                try:
                    max_cached_block = int(cache['block'].max())
                    logger.debug('%s %s is cached thru block %s', partner.name, self.name, max_cached_block)
                    start_block = max_cached_block + 1 if partner.start_block is None else max(partner.start_block, max_cached_block + 1)
                except KeyError:
                    start_block = partner.start_block
                    logger.debug('no harvests cached for %s %s', partner.name, self.name)
                logger.debug(f'start block: {start_block}')
            else:
                start_block = partner.start_block
            
            futs = []
            async for protocol_fees in self.protocol_fees(start_block=start_block):
                futs.append(asyncio.create_task(process_harvests(self, protocol_fees)))
            data = [data for data in await asyncio.gather(*futs) if data is not None]
            data = pd.concat(data) if data else DataFrame()
            
            if use_postgres_cache:
                await threads.run(cache_data, data)
                data = pd.concat([cache, data])
            
            return data
    
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

    async def protocol_fees(self, start_block: int = None) -> AsyncGenerator[Dict[int,Decimal], None]:
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
            
        async for logs in get_logs_asap_generator(self.vault, topics, from_block=logs_start_block):
            yield {log.block_number: Decimal(log['value']) / Decimal(vault.scale) for log in decode_logs(logs) if should_include(log)}

    async def balances(self, blocks: Tuple[int,...]) -> List[Decimal]:
        balances = await asyncio.gather(*[self.vault_contract.balanceOf.coroutine(self.wrapper, block_identifier=block) for block in blocks])
        return [Decimal(balance) / Decimal(self.scale) for balance in balances]

    async def total_supplies(self, blocks: Tuple[int,...]) -> List[Decimal]:
        total_supply_cached = _get_cached_total_supply_fn(self.vault_contract)
        supplies = await asyncio.gather(*[total_supply_cached(block_identifier = block) for block in blocks])
        return [Decimal(supply) / Decimal(self.scale) for supply in supplies]

    async def vault_prices(self, blocks: Tuple[int,...]) -> List[Decimal]:
        return [Decimal(price) for price in await asyncio.gather(*[get_price(self.vault, block=block, sync=False) for block in blocks])]


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
        balances = await asyncio.gather(*[self.get_balance(block) for block in blocks])
        return [Decimal(balance or 0) / Decimal(self.scale) for balance in balances]
    
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
        if chain.id == Network.Mainnet:
            return await Contract.coroutine("0xd96f48665a1410C0cd669A88898ecA36B9Fc2cce")
        raise UnsupportedNetwork()

    async def balances(self, blocks) -> List[Decimal]:
        balances = await asyncio.gather(*[self.get_balance(block) for block in blocks])
        return [Decimal(balance or 0) / Decimal(self.scale) for balance in balances]
    
    async def get_balance(self, block) -> Optional[int]:
        degenbox = await self.degenbox
        try:
            return await degenbox.balanceOf.coroutine(self.vault, self.wrapper, block_identifier=block)
        except Exception as e:
            continue_if_call_reverted(e)


@dataclass
class WildcardWrapper:
    """
    Automatically find and generate all valid (wrapper, vault) pairs.
    """

    name: str
    wrapper: Union[str, List[str]]  # can unpack multiple wrappers

    async def unwrap(self) -> List[Wrapper]:
        registry = Registry()
        wrappers = [self.wrapper] if isinstance(self.wrapper, str) else self.wrapper
        topics = construct_event_topic_set(
            filter_by_name('Transfer', registry.vaults[0].vault.abi)[0],
            web3.codec,
            {'receiver': wrappers},
        )
        addresses = [str(vault.vault) for vault in registry.vaults]
        from_block = min(await asyncio.gather(*[threads.run(contract_creation_block, address) for address in addresses]))

        # wrapper -> {vaults}
        deposits = defaultdict(set)
        async for logs in get_logs_asap_generator(addresses, topics, from_block):
            for log in decode_logs(logs):
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

    async def unwrap(self) -> List[Wrapper]:
        registry = await Contract.coroutine(self.wrapper)
        wrappers = await asyncio.gather(*[Contract.coroutine(wrapper) for wrapper in await registry.viewRegistry.coroutine()])
        info = await asyncio.gather(*[asyncio.gather(ERC20(wrapper, asynchronous=True).name, wrapper.vault.coroutine()) for wrapper in wrappers])
        return [Wrapper(name=name, vault=vault, wrapper=wrapper) for wrapper, (name, vault) in zip(wrappers, info)]


@dataclass
class YApeSwapFactoryWrapper(WildcardWrapper):
    name: str
    wrapper: str

    async def unwrap(self) -> List[Wrapper]:
        factory = await Contract.coroutine(self.wrapper)
        pairs = await asyncio.gather(*[factory.allPairs.coroutine(i) for i in range(await factory.allPairsLength.coroutine())])
        pairs = await asyncio.gather(*[Contract.coroutine(pair) for pair in pairs])
        ratios = await asyncio.gather(*[pair.farmingRatio.coroutine() for pair in pairs])
        # pools with ratio.min > 0 deploy to yearn vaults
        farming = [str(pair) for pair, ratio in zip(pairs, ratios) if ratio['min'] > 0]
        return await WildcardWrapper(self.name, farming).unwrap()


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
    
    async def get_balance(self, credit_account: Address, block: int) -> Decimal:
        async with granular_balance_semaphore:
            return await self.vault_contract.balanceOf.coroutine(credit_account, block_identifier=block) / Decimal(self.scale)
    
    async def get_vault_depositors(self, block: int) -> Set[Address]:
        from_block = await contract_creation_block_async(self.wrapper)
        return {
            transfer['receiver']
            async for logs in get_logs_asap_generator(self.vault, [ERC20_TRANSFER_EVENT_HASH], from_block=from_block, to_block=block, chronological=False)
            for transfer in decode_logs(logs)
        }
        
        
class InverseWrapper(Wrapper):
    def __hash__(self) -> int:
        return hash(self.vault + self.wrapper)
    
    async def balances(self, blocks) -> List[Decimal]:
        return await asyncio.gather(*[self.get_tvl(block) for block in blocks])
    
    async def get_tvl(self, block: int) -> Decimal:
        # We use futs instead of gather here so we can process logs as they come in vs waiting for all of them before proceeding
        futs = [asyncio.create_task(self.get_balance(escrow, block)) async for escrow in self.get_escrows(block)]
        return sum(await asyncio.gather(*futs))
    
    async def get_balance(self, escrow: Address, block: int) -> Decimal:
        escrow = await Contract.coroutine(escrow)
        async with granular_balance_semaphore:
            return await escrow.balance.coroutine(block_identifier=block) / Decimal(self.scale)
    
    async def get_escrows(self, block) -> AsyncGenerator[Address, None]:
        wrapper_contract = await Contract.coroutine(self.wrapper)
        async for logs in get_logs_asap_generator(self.wrapper, [wrapper_contract.topics['CreateEscrow']], to_block=block, chronological=False):
            for event in decode_logs(logs):
                yield event['escrow']
    

class DelegatedDepositWrapper(Wrapper):
    """
    Set `wrapper` equal to the the partner's partnerId from the YearnPartnerTracker contract.
    """

    async def balances(self, blocks: List[Block]) -> List[Decimal]:
        balances = await asyncio.gather(*[self.get_balance_at_block(block) for block in blocks])
        scale = Decimal(self.scale)
        return [balance / scale for balance in balances]
            
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
        return Decimal(total)
        

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

granular_balance_semaphore = asyncio.Semaphore(50_000)

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
            

    @async_cached_property
    async def flat_wrappers(self) -> List[Wrapper]:
        # unwrap wildcard wrappers to a flat list
        flat_wrappers = []
        for wrapper in self.wrappers:
            if isinstance(wrapper, Wrapper):
                flat_wrappers.append(wrapper)
            elif isinstance(wrapper, WildcardWrapper) or isinstance(wrapper, DelegatedDepositWildcardWrapper):
                flat_wrappers.extend(await wrapper.unwrap())
        return flat_wrappers

    async def process(self, use_postgres_cache: bool = USE_POSTGRES_CACHE) -> Tuple[DataFrame,DataFrame]:
        # TODO Optimize this a bit better.
        # snapshot wrapper share at each harvest
        wrappers = []
        data = await asyncio.gather(*[wrapper.get_data(self, use_postgres_cache) for wrapper in await self.flat_wrappers])
        for wrapper, data in zip(await self.flat_wrappers, data):
            try:
                data = data.set_index('block')
            except KeyError:
                logger.info('no fees for %s', wrapper.name)
                continue

            # TODO: save a csv for reporting
            wrappers.append(data)

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

async def process_harvests(wrapper, protocol_fees) -> Optional[DataFrame]:
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
        return wrap
    except ValueError as e:
        if str(e) != 'not enough values to unpack (expected 2, got 0)':
            raise
        return None

@lru_cache(maxsize=None)
def _get_cached_total_supply_fn(vault: Contract) -> Callable[[], int]:
    return alru_cache(maxsize=None)(vault.totalSupply.coroutine)