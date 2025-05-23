import asyncio
import itertools
import logging
import time
from asyncio import create_task
from collections import OrderedDict
from functools import cached_property
from typing import AsyncIterator, Awaitable, Dict, List, NoReturn, overload

import a_sync
import dank_mids
import inflection
from a_sync import cgather, igather
from async_property import async_cached_property, async_property
from brownie import chain, web3
from brownie.network.event import _EventItem
from dank_mids import dank_web3
from eth_typing import ChecksumAddress
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y import Contract, Network, get_price
from y._decorators import stuck_coro_debugger
from y.constants import CHAINID
from y.utils.events import Events, ProcessedEvents

from yearn.decorators import set_exc, wait_or_exit_before
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall_async
from yearn.utils import Singleton
from yearn.v2.vaults import Vault

logger = logging.getLogger(__name__)

DEPRECATED_VAULTS = {
    Network.Mainnet: [
        "0x8a0889d47f9Aa0Fac1cC718ba34E26b867437880", # rekt st-yCRV (vyper / etherscan verification issue)
        "0x61f46C65E403429266e8b569F23f70dD75d9BeE7", # rekt lp-yCRV (vyper / etherscan verification issue)
    ]
}

# populate rekt vaults here
TEMP_REKT_VAULTS = {
    Network.Optimism: [
        "0x9E724b3f65b509326A4F5Ec90D4689BeE6b6C78e", # ERN-USDC, issue with pricing
    ]
}

VaultName = str

class Registry(metaclass=Singleton):
    def __init__(self, include_experimental=True):
        self.releases = {}  # api_version => template
        self.governance = None
        self.tags = {}
        self.include_experimental = include_experimental
        self._done = a_sync.Event(name=f"{self.__module__}.{self.__class__.__name__}._done")
        self._registries = []
        self._vaults = {}  # address -> Vault
        self._experiments = {}  # address => Vault
        self._removed = {}
        self._staking_pools = {} # vault address -> staking_pool address
    
    @async_cached_property
    @stuck_coro_debugger
    async def registries(self) -> List[Contract]:
        if CHAINID == Network.Mainnet:
            registries = await self.load_from_ens()
        elif CHAINID == Network.Gnosis:
            registries = [await Contract.coroutine('0xe2F12ebBa58CAf63fcFc0e8ab5A61b145bBA3462')]
        elif CHAINID == Network.Fantom:
            registries = [await Contract.coroutine('0x727fe1759430df13655ddb0731dE0D0FDE929b04')]
        elif CHAINID == Network.Arbitrum:
            registries = [await Contract.coroutine('0x3199437193625DCcD6F9C9e98BDf93582200Eb1f')]
        elif CHAINID == Network.Optimism:
            registries = await cgather(
                Contract.coroutine('0x79286Dd38C9017E5423073bAc11F53357Fc5C128'),
                Contract.coroutine('0x81291ceb9bB265185A9D07b91B5b50Df94f005BF'),
                Contract.coroutine('0x8ED9F6343f057870F1DeF47AaE7CD88dfAA049A8'), # StakingRewardsRegistry
            )
        elif CHAINID == Network.Base:
            registries = [await Contract.coroutine('0xF3885eDe00171997BFadAa98E01E167B53a78Ec5')]
        else:
            raise UnsupportedNetwork('yearn v2 is not available on this network')
        
        for r in registries[:]:
            if hasattr(r, 'releaseRegistry') and "ReleaseRegistryUpdated" in r.topics:
                # Add all past and present Release Registries
                events = Events(addresses=r, topics=[r.topics['ReleaseRegistryUpdated']])
                for rr in set(await igather([
                    create_task(Contract.coroutine(list(event.values())[0]))
                    async for event in events.events(to_block=await dank_mids.eth.block_number)
                ])):
                    registries.append(rr)
                    logger.debug("release registry %s found for registry %s", rr, r)
                logger.info('registry loaded')
                events._task.cancel()
        return registries

    @stuck_coro_debugger
    async def load_from_ens(self):
        # track older registries to pull experiments
        resolver = await Contract.coroutine('0x4976fb03C32e5B8cfe2b6cCB31c09Ba78EBaBa41')
        topics = construct_event_topic_set(
            filter_by_name('AddressChanged', resolver.abi)[0],
            web3.codec,
            {'node': web3.ens.namehash('v2.registry.ychad.eth')},
        )
        events = Events(addresses=resolver, topics=topics)
        registries = [
            asyncio.create_task(
                coro=Contract.coroutine(event['newAddress'].hex()),
                name=f"load registry {event['newAddress']}",
            )
            async for event in events.events(to_block = await dank_mids.eth.block_number)
        ]            
        if registries:
            registries = await igather(registries)
        logger.info('loaded %d registry versions', len(registries))
        events._task.cancel()
        return registries

    @async_property
    @stuck_coro_debugger
    @wait_or_exit_before
    async def vaults(self) -> List[Vault]:
        return list(self._vaults.values())

    @async_property
    @stuck_coro_debugger
    @wait_or_exit_before
    async def experiments(self) -> List[Vault]:
        return list(self._experiments.values())

    @async_property
    @stuck_coro_debugger
    @wait_or_exit_before
    async def removed(self) -> List[Vault]:
        return list(self._removed.values())

    @async_property
    @stuck_coro_debugger
    @wait_or_exit_before
    async def staking_pools(self) -> Dict:
        return self._staking_pools

    def __repr__(self) -> str:
        return f"<Registry chain={CHAINID} releases={len(self.releases)} vaults={len(self._vaults)} experiments={len(self._experiments)}>"
    
    @set_exc
    async def load_events(self) -> NoReturn:
        if not self._done.is_set():
            start = time.time()
            events: RegistryEvents = await self._events
            async for _ in events.events(to_block = await dank_mids.eth.block_number):
                self._filter_vaults()
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded v2 registry in %.3fs", time.time() - start)

    def process_events(self, events):
        temp_rekt_vaults = TEMP_REKT_VAULTS.get(CHAINID, [])

        for event in events:
            if "vault" in event and event["vault"] in temp_rekt_vaults:
                logger.warning(f"skipping temp rekt vault {event['vault']}")
                continue

            # hack to make camels to snakes
            event._ordered = [OrderedDict({inflection.underscore(k): v for k, v in od.items()}) for od in event._ordered]
            logger.debug("starting to process %s for %s: %s", event.name, event.address, dict(event))
            if event.name == "NewGovernance":
                self.governance = event["governance"]

            if event.name == "NewRelease":
                self.releases[event["api_version"]] = Contract(event["template"])

            if event.name == "NewVault":
                # experiment was endorsed
                if event["vault"] in self._experiments:
                    vault = self._experiments.pop(event["vault"])
                    vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                    self._vaults[event["vault"]] = vault
                    logger.debug("endorsed vault %s %s", vault.vault, vault.name)
                # we already know this vault from another registry
                elif event["vault"] not in self._vaults:
                    vault = self.vault_from_event(event)
                    vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                    self._vaults[event["vault"]] = vault
                    logger.debug("new vault %s %s", vault.vault, vault.name)

            if self.include_experimental and event.name == "NewExperimentalVault":
                vault = self.vault_from_event(event)
                vault.name = f"{vault.vault.symbol()} {event['api_version']} {event['vault'][:8]}"
                self._experiments[event["vault"]] = vault
                logger.debug("new experiment %s %s", vault.vault, vault.name)

            if event.name == "VaultTagged":
                if event["tag"] == "Removed":
                    self._remove_vault(event["vault"])
                    logger.debug("Removed vault %s", event["vault"])
                else:
                    self.tags[event["vault"]] = event["tag"]

            if event.name == "StakingPoolAdded":
                self._staking_pools[event["token"]] = event["staking_pool"]
            logger.debug("done processing %s for %s: %s", event.name, event.address, dict(event))


    def vault_from_event(self, event):
        api_version = event["api_version"]
        contract = Contract.from_abi(
            "Vault", 
            event["vault"], 
            self.releases[api_version].abi,
        )
        return Vault(
            vault=dank_mids.patch_contract(contract, dank_web3),
            token=event["token"],
            api_version=api_version,
            registry=self,
        )

    @stuck_coro_debugger
    async def describe(self, block=None) -> Dict[VaultName, Dict]:
        return await a_sync.gather({
            vault.name: asyncio.create_task(vault.describe(block=block)) 
            async for vault in self.active_vaults_at(block, iter=True)
        })

    @stuck_coro_debugger
    async def total_value_at(self, block=None):
        vaults = await self.active_vaults_at(block)
        prices, results = await cgather(
            igather(get_price(str(vault.token), block=block, sync=False) for vault in vaults),
            fetch_multicall_async(*([vault.vault, "totalAssets"] for vault in vaults), block=block),
        )
        return {vault.name: assets * price / vault.scale for vault, assets, price in zip(vaults, results, prices)}

    @overload
    def active_vaults_at(self, block=None, iter = False) -> Awaitable[List[Vault]]:...
    @overload
    def active_vaults_at(self, block=None, iter = True) -> AsyncIterator[Vault]:...
    def active_vaults_at(self, block=None, iter: bool = False):
        if iter:
            return self._active_vaults_at_iter(block=block)
        else: 
            return self._active_vaults_at(block=block)
        
    @stuck_coro_debugger
    async def _active_vaults_at(self, block=None) -> List[Vault]:
        self._task
        events: RegistryEvents = await self._events
        await events.events(to_block = block or events._init_block)
        self._filter_vaults()
        vaults = list(itertools.chain(self._vaults.values(), self._experiments.values()))
        return [vault for vault, active in zip(vaults, await igather(vault.is_active(block) for vault in vaults)) if active]
    
    async def _active_vaults_at_iter(self, block=None) -> AsyncIterator[Vault]:
        # ensure loader task is running
        self._task
        events: RegistryEvents = await self._events
        # make sure the events are loaded thru now before proceeding
        await events.events(to_block=block or events._init_block)
        self._filter_vaults()
        
        vaults: List[Vault] = list(itertools.chain(self._vaults.values(), self._experiments.values()))
        
        i = 0  # TODO figure out why we need this here
        while len(vaults) == 0:
            await asyncio.sleep(6)
            vaults = list(itertools.chain(self._vaults.values(), self._experiments.values()))
            i += 1  
            if i >= 20:
                logger.error("we're stuck")
        
        async for vault, active in a_sync.as_completed({vault: vault.is_active(block) for vault in vaults}, aiter=True):
            if active:
                yield vault

    @async_cached_property
    async def _events(self) -> "RegistryEvents":
        return RegistryEvents(self, await self.registries)
    
    @cached_property
    def _task(self) -> asyncio.Task:
        return asyncio.create_task(self.load_events())
    
    def _filter_vaults(self) -> None:
        if CHAINID in DEPRECATED_VAULTS:
            for vault in DEPRECATED_VAULTS[CHAINID]:
                self._remove_vault(vault, save=False)

    def _remove_vault(self, address: ChecksumAddress, save: bool = True) -> None:
        v = self._vaults.pop(address, None)
        e = self._experiments.pop(address, None)
        self.tags.pop(address, None)
        if save:
            if v and e:
                raise NotImplementedError(v, e)
            if v or e:
                self._removed[address] = v or e
            else:
                raise NotImplementedError(v, e, address)
        logger.debug('removed %s', address)
        logger.debug("Removed vault %s", address)


class RegistryEvents(ProcessedEvents[_EventItem]):
    __slots__ = "_init_block", "_registry"
    def __init__(self, registry: Registry, registries: List[Contract]):
        assert registries, registries
        self._init_block = chain.height
        self._registry = registry
        super().__init__(addresses=registries)
    def _process_event(self, event: _EventItem) -> _EventItem:
        # hack to make camels to snakes
        event._ordered = [OrderedDict({inflection.underscore(k): v for k, v in od.items()}) for od in event._ordered]
        logger.debug("starting to process %s for %s: %s", event.name, event.address, dict(event))
        if event.name == "NewGovernance":
            self._registry.governance = event["governance"]

        if event.name == "NewRelease":
            self._registry.releases[event["api_version"]] = Contract(event["template"])

        if event.name == "NewVault":
            # experiment was endorsed
            if event["vault"] in self._registry._experiments:
                vault = self._registry._experiments.pop(event["vault"])
                vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                self._registry._vaults[event["vault"]] = vault
                logger.debug("endorsed vault %s %s", vault.vault, vault.name)
            # we already know this vault from another registry
            elif event["vault"] not in self._registry._vaults:
                vault = self._registry.vault_from_event(event)
                vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                self._registry._vaults[event["vault"]] = vault
                logger.debug("new vault %s %s", vault.vault, vault.name)

        if self._registry.include_experimental and event.name == "NewExperimentalVault":
            vault = self._registry.vault_from_event(event)
            vault.name = f"{vault.vault.symbol()} {event['api_version']} {event['vault'][:8]}"
            self._registry._experiments[event["vault"]] = vault
            logger.debug("new experiment %s %s", vault.vault, vault.name)

        if event.name == "VaultTagged":
            if event["tag"] == "Removed":
                self._registry._remove_vault(event["vault"])
            else:
                self._registry.tags[event["vault"]] = event["tag"]

        if event.name == "StakingPoolAdded":
            self._registry._staking_pools[event["token"]] = event["staking_pool"]
        logger.debug("done processing %s for %s: %s", event.name, event.address, dict(event))
        return event
