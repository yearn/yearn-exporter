import asyncio
import logging
import threading
import time
from collections import OrderedDict
from typing import List, Tuple

import dask
import inflection
from async_property import async_property
from brownie import Contract, chain, web3
from dank_mids.brownie_patch import patch_contract
from dask.delayed import Delayed
from joblib import Parallel, delayed
from multicall.utils import await_awaitable
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y.contracts import contract_creation_block, contract_creation_block_async
from y.datatypes import Block
from y.networks import Network
from y.prices import magic
from y.utils.dank_mids import dank_w3
from y.utils.events import get_logs_asap_generator

from yearn.events import decode_logs, get_logs_asap
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall, fetch_multicall_async
from yearn.utils import Singleton, contract
from yearn.v2.strategies import Strategy
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
        self.releases = {}  # api_version => template
        self._vaults = {}  # address -> Vault
        self._experiments = {}  # address => Vault
        self.governance = None
        self.tags = {}
        self._watch_events_forever = watch_events_forever
        self.include_experimental = include_experimental
        self.registries = self.load_registry()
        # load registry state in the background
        self._loading = asyncio.Event()
        self._done = asyncio.Event()

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
            return [contract('0x79286Dd38C9017E5423073bAc11F53357Fc5C128'), contract('0x81291ceb9bB265185A9D07b91B5b50Df94f005BF')]
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
        logger.info('loaded %d registry versions', len(events))
        return [contract(event['newAddress'].hex()) for event in events]

    @async_property
    async def vaults(self) -> List[Vault]:
        await self.load_vaults()
        return list(self._vaults.values())

    @async_property
    async def experiments(self) -> List[Vault]:
        await self.load_vaults()
        return list(self._experiments.values())

    def __repr__(self) -> str:
        try:
            return f"<Registry chain={chain.id} releases={len(self.releases)} vaults={len(await_awaitable(self.vaults))} experiments={len(await_awaitable(self.experiments))}>"
        except RuntimeError:
            return f"<Registry chain={chain.id} releases={len(self.releases)}>"

    #@wait_or_exit_after
    #def load_vaults(self):
    #    if not self._thread._started.is_set():
    #        self._thread.start()
    
    async def load_vaults(self):
        if not self._loading.is_set():
            asyncio.create_task(self.watch_events())
        await self._done.wait()
    
    async def watch_events(self):
        if self._loading.is_set():
            # Escape hatch so we don't end up with multiple watcher tasks.
            return
        self._loading = True
        block = await dank_w3.eth.block_number
        start = time.time()
        await asyncio.gather(*[self._watch_events_for_registry(reg, to_block=block, run_forever=False) for reg in self.registries])
        self._done.set()
        logger.info("loaded v2 registry in %.3fs", time.time() - start)
        await asyncio.gather(*[self._watch_events_for_registry(reg, from_block=block+1, run_forever=self._watch_events_forever) for reg in self.registries])

    async def _watch_events_for_registry(self, registry: Contract, from_block=None, to_block=None, run_forever: bool = False):
        async for logs in get_logs_asap_generator(registry.address, from_block=from_block, to_block=to_block, chronological=True, run_forever=run_forever):
            self.process_logs(logs)


    '''
    @sentry_catch_all
    def watch_events(self):
        start = time.time()
        self.log_filter = create_filter([str(addr) for addr in self.registries])
        logs = self.log_filter.get_all_entries()
        while True:
            self.process_events(decode_logs(logs))
            self._filter_vaults()
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded v2 registry in %.3fs", time.time() - start)
            if not self._watch_events_forever:
                return
            time.sleep(300)

            # read new logs at end of loop
            logs = self.log_filter.get_new_entries()'''

    def process_logs(self, logs):
        events = decode_logs(logs)
        for event in events:
            # hack to make camels to snakes
            event._ordered = [OrderedDict({inflection.underscore(k): v for k, v in od.items()}) for od in event._ordered]
            logger.debug("%s %s %s", event.address, event.name, dict(event))
            if event.name == "NewGovernance":
                self.governance = event["governance"]

            if event.name == "NewRelease":
                self.releases[event["api_version"]] = contract(event["template"])

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

    def vault_from_event(self, event):
        return Vault(
            vault=patch_contract(Contract.from_abi("Vault", event["vault"], self.releases[event["api_version"]].abi), dank_w3),
            token=event["token"],
            api_version=event["api_version"],
            registry=self,
            watch_events_forever=self._watch_events_forever,
        )

    # NOTE remove this, not used anywhere?
    def load_harvests(self):
        vaults = await_awaitable(self.vaults) + await_awaitable(self.experiments)
        Parallel(8, "threading")(delayed(vault.load_harvests)() for vault in vaults)

    async def _describe_delayed(self, vaults, results) -> dict:
        return {vault.name: result for vault, result in zip(vaults, results)}

    def describe_delayed(self, vaults: List[Tuple[Vault, List[Strategy]]], block: Block) -> Delayed:
        return dask.delayed(self._describe_delayed, nout=len(vaults))(vaults, [(vault.describe_delayed)(strategies, block=block) for vault, strategies in vaults])

    async def describe(self, block=None):
        vaults = await self.active_vaults_at(block)
        results = await asyncio.gather(*[vault.describe(block=block) for vault in vaults])
        return {vault.name: result for vault, result in zip(vaults, results)}

    async def total_value_at(self, block=None):
        vaults = await self.active_vaults_at(block)
        prices, results = await asyncio.gather(
            asyncio.gather(*[magic.get_price_async(str(vault.token), block=block) for vault in vaults]),
            fetch_multicall_async(*[[vault.vault, "totalAssets"] for vault in vaults], block=block),
        )
        return {vault.name: assets * price / vault.scale for vault, assets, price in zip(vaults, results, prices)}

    async def active_vaults_at(self, block=None) -> List[Vault]:
        vaults, experiments = await asyncio.gather(self.vaults, self.experiments)
        vaults += experiments
        if block:
            blocks = await asyncio.gather(*[contract_creation_block_async(str(vault.vault)) for vault in vaults])
            vaults = [vault for vault, deploy_block in zip(vaults, blocks) if deploy_block <= block]
        # fixes edge case: a vault is not necessarily initialized on creation
        activations = await fetch_multicall_async(*[[vault.vault, 'activation'] for vault in vaults], block=block)
        return [vault for vault, activation in zip(vaults, activations) if activation]
    
    def _active_vaults_at_sync(self, block=None):
        vaults = await_awaitable(self.vaults) + await_awaitable(self.experiments)
        if block:
            blocks = Parallel(8, 'threading')(delayed(contract_creation_block)(str(vault.vault)) for vault in vaults)
            #blocks = await asyncio.gather(*[contract_creation_block_async(str(vault.vault)) for vault in vaults])
            vaults = [vault for vault, deploy_block in zip(vaults, blocks) if deploy_block <= block]
        # fixes edge case: a vault is not necessarily initialized on creation
        activations = fetch_multicall(*[[vault.vault, 'activation'] for vault in vaults], block=block)
        return [vault for vault, activation in zip(vaults, activations) if activation]

    def _filter_vaults(self):
        if chain.id in DEPRECATED_VAULTS:
            for vault in DEPRECATED_VAULTS[chain.id]:
                self._remove_vault(vault)

    def _remove_vault(self, address):
        self._vaults.pop(address, None)
        self._experiments.pop(address, None)
        self.tags.pop(address, None)
