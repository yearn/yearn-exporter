import asyncio
import logging
import time
from collections import OrderedDict
from contextlib import suppress
from typing import Dict, List
from brownie.network.event import _EventItem, EventDict

import a_sync
import inflection
from async_property import async_property
from brownie import chain, web3
from joblib import Parallel, delayed
from multicall.utils import await_awaitable
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y import ERC20, Contract
from y.contracts import contract_creation_block_async
from y.networks import Network
from y.prices import magic
from y.utils.dank_mids import dank_w3
from y.utils.events import get_logs_asap_generator

from yearn.events import get_logs_asap, decode_logs
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall_async
from yearn.utils import Singleton, contract
from yearn.v2.vaults import Vault

logger = logging.getLogger(__name__)

DEPRECATED_VAULTS = {
    Network.Mainnet: [
        "0x8a0889d47f9Aa0Fac1cC718ba34E26b867437880", # rekt st-yCRV (vyper / etherscan verification issue)
        "0x61f46C65E403429266e8b569F23f70dD75d9BeE7", # rekt lp-yCRV (vyper / etherscan verification issue)
    ]
}

class Registry(metaclass=Singleton):
    def __init__(self, watch_events_forever=True, include_experimental=True):
        self._vaults = {}  # address -> Vault
        self._experiments = {}  # address => Vault
        self._staking_pools = {} # vault address -> staking_pool address
        self.governance = None
        self.tags = {}
        self._watch_events_forever = watch_events_forever
        self.include_experimental = include_experimental
        self.registries = self.load_registry()
        self._task = None
        self._done = a_sync.Event()
        self._lock = asyncio.Lock()
        self.__cache_futs = []

    def load_registry(self):
        if chain.id == Network.Mainnet:
            return self.load_from_ens()
        elif chain.id == Network.Gnosis:
            return [contract('0xe2F12ebBa58CAf63fcFc0e8ab5A61b145bBA3462')]
        elif chain.id == Network.Fantom:
            return [contract('0x727fe1759430df13655ddb0731dE0D0FDE929b04')]
        elif chain.id == Network.Arbitrum:
            return [contract('0x3199437193625DCcD6F9C9e98BDf93582200Eb1f')]
        elif chain.id == Network.Optimism:
            return [
                contract('0x79286Dd38C9017E5423073bAc11F53357Fc5C128'),
                contract('0x81291ceb9bB265185A9D07b91B5b50Df94f005BF'),
                contract('0x8ED9F6343f057870F1DeF47AaE7CD88dfAA049A8'), # StakingRewardsRegistry
            ]
        else:
            raise UnsupportedNetwork('yearn v2 is not available on this network')

    def load_from_ens(self):
        # track older registries to pull experiments
        resolver = contract('0x4976fb03C32e5B8cfe2b6cCB31c09Ba78EBaBa41')
        topics = construct_event_topic_set(
            filter_by_name('AddressChanged', resolver.abi)[0],
            web3.codec,
            {'node': web3.ens.namehash('v2.registry.ychad.eth')},
        )
        events = decode_logs(get_logs_asap(str(resolver), topics))
        registries = []
        for event in events:
            r = contract(event['newAddress'].hex())
            registries.append(r)
            if hasattr(r, 'releaseRegistry'):
                rr = contract(r.releaseRegistry())
                registries.append(rr)
        logger.info('loaded %d registry versions', len(registries))
        return registries

    @async_property
    async def vaults(self) -> List[Vault]:
        await self.load_vaults()
        return list(self._vaults.values())

    @async_property
    async def experiments(self) -> List[Vault]:
        await self.load_vaults()
        return list(self._experiments.values())

    @async_property
    async def staking_pools(self) -> Dict:
        await self.load_vaults()
        return self._staking_pools

    def __repr__(self) -> str:
        if self._done.is_set():
            vaults = len(self._vaults)
            experiments = len(self._experiments)
        else:
            vaults = experiments = "[...]"
        return f"<Registry chain={chain.id} vaults={vaults} experiments={experiments}>"

    async def load_vaults(self):
        async with self._lock:
            if self._task is None:
                self._task = asyncio.create_task(self.watch_events())
            while not self._task.done():
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._done.wait(), 5)
                    return
            if e := self._task.exception():
                raise e

    async def watch_events(self):
        start = time.time()
        from_block = None
        height = await dank_w3.eth.block_number
        logs = []
        async for lgs in get_logs_asap_generator([str(addr) for addr in self.registries], from_block=from_block, to_block=height, chronological=True):
            logs.extend(lgs)
            self._load_caches(decode_logs(lgs))
            
        events = decode_logs(logs)
        await asyncio.gather(*self.__cache_futs)
        del self.__cache_futs
        await self.process_events(events)
        self._filter_vaults()
        
        self._done.set()
        logger.info("loaded v2 registry in %.3fs", time.time() - start)
        if not self._watch_events_forever:
            return
        
        async for logs in get_logs_asap_generator([str(addr) for addr in self.registries], from_block=height + 1, chronological=True, run_forever=True):
            await self.process_events(decode_logs(logs))
            self._filter_vaults()
    
    def _load_caches(self, events: EventDict):
        # We load some caches here to take advantage of batching
        event: _EventItem
        for event in events:
            if event.name == "NewRelease":
                self.__cache_futs.append(asyncio.create_task(Contract.coroutine(event['template'])))
            if event.name == "NewVault":
                self.__cache_futs.append(asyncio.create_task(Contract.coroutine(event['vault'])))
                self.__cache_futs.append(asyncio.create_task(_get_symbol(event['vault'])))

    async def process_events(self, events: EventDict):
        event: _EventItem
        for event in events:
            # hack to make camels to snakes
            event._ordered = [OrderedDict({inflection.underscore(k): v for k, v in od.items()}) for od in event._ordered]
            
            logger.debug("%s %s %s %s", event.block_number, event.address, event.name, dict(event))
            if event.name == "NewGovernance":
                self.governance = event["governance"]
                
            if event.name == "NewVault":
                vault_address = event["vault"]
                version = event["api_version"]
                symbol = await _get_symbol(vault_address)
                # experiment was endorsed
                if vault_address in self._experiments:
                    vault = self._experiments.pop(vault_address)
                    vault.name = f"{symbol} {version}"
                    self._vaults[vault_address] = vault
                    logger.debug("endorsed vault %s %s", vault.vault, vault.name)
                # we already know this vault from another registry
                elif vault_address not in self._vaults:
                    vault = await self.vault_from_event(event)
                    vault.name = f"{symbol} {version}"
                    self._vaults[vault_address] = vault
                    logger.debug("new vault %s %s", vault.vault, vault.name)

            if self.include_experimental and event.name == "NewExperimentalVault":
                vault = await self.vault_from_event(event)
                vault.name = f"{symbol} {version} {event['vault'][:8]}"
                self._experiments[vault_address] = vault
                logger.debug("new experiment %s %s", vault.vault, vault.name)

            if event.name == "VaultTagged":
                if event["tag"] == "Removed":
                    self._remove_vault(vault_address)
                    logger.debug("Removed vault %s", vault_address)
                else:
                    self.tags[vault_address] = event["tag"]

            if event.name == "StakingPoolAdded":
                self._staking_pools[event["token"]] = event["staking_pool"]

    async def vault_from_event(self, event):
        return Vault(
            vault=await Contract.coroutine(event["vault"]),
            token=event["token"],
            api_version=event["api_version"],
            registry=self,
            watch_events_forever=self._watch_events_forever,
        )

    def load_harvests(self):
        vaults, experiments = await_awaitable(asyncio.gather(self.vaults, self.experiments))
        Parallel(1, "threading")(delayed(vault.load_harvests)() for vault in vaults + experiments)

    async def describe(self, block=None):
        vaults = await self.active_vaults_at(block)
        results = await asyncio.gather(*[vault.describe(block=block) for vault in vaults])
        return {vault.name: result for vault, result in zip(vaults, results)}

    async def total_value_at(self, block=None):
        vaults = await self.active_vaults_at(block)
        prices, results = await asyncio.gather(
            asyncio.gather(*[magic.get_price(str(vault.token), block=block, sync=False) for vault in vaults]),
            fetch_multicall_async(*[[vault.vault, "totalAssets"] for vault in vaults], block=block),
        )
        return {vault.name: assets * price / vault.scale for vault, assets, price in zip(vaults, results, prices)}

    async def active_vaults_at(self, block=None):
        vaults, experiments = await asyncio.gather(self.vaults, self.experiments)
        vaults += experiments
        if block:
            blocks = await asyncio.gather(*[contract_creation_block_async(str(vault.vault)) for vault in vaults])
            vaults = [vault for vault, deploy_block in zip(vaults, blocks) if deploy_block <= block]
        # fixes edge case: a vault is not necessarily initialized on creation
        activations = await fetch_multicall_async(*[[vault.vault, 'activation'] for vault in vaults], block=block)
        return [vault for vault, activation in zip(vaults, activations) if activation]

    def _filter_vaults(self):
        if chain.id in DEPRECATED_VAULTS:
            for vault in DEPRECATED_VAULTS[chain.id]:
                self._remove_vault(vault)

    def _remove_vault(self, address):
        self._vaults.pop(address, None)
        self._experiments.pop(address, None)
        self.tags.pop(address, None)

async def _get_symbol(vault):
    # we need this to be a coro
    return await ERC20(vault, asynchronous=True).symbol
