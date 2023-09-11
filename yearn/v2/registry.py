import asyncio
import logging
import threading
import time
from collections import OrderedDict
from typing import Dict, List

import inflection
from brownie import Contract, chain, web3
from dank_mids.brownie_patch import patch_contract
from joblib import Parallel, delayed
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from y.contracts import contract_creation_block_async
from y.exceptions import NodeNotSynced
from y.networks import Network
from y.prices import magic
from y.utils.dank_mids import dank_w3

from yearn.decorators import (sentry_catch_all, wait_or_exit_after,
                              wait_or_exit_before)
from yearn.events import decode_logs, get_logs_asap
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
        self.releases = {}  # api_version => template
        self._vaults = {}  # address -> Vault
        self._experiments = {}  # address => Vault
        self._staking_pools = {} # vault address -> staking_pool address
        self.governance = None
        self.tags = {}
        self._watch_events_forever = watch_events_forever
        self.include_experimental = include_experimental
        self.registries = self.load_registry()
        # load registry state in the background
        self._done = threading.Event()
        self._has_exception = False
        self._thread = threading.Thread(target=self.watch_events, daemon=True)
        self._thread.start()

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
                logs = get_logs_asap([str(addr) for addr in self.registries], r.topics["ReleaseRegistryUpdated"])
                # Add all past and present Release Registries
                registries.extend({contract(event['address']) for event in decode_logs(logs)})
        logger.info('loaded %d registry versions', len(registries))
        return registries

    @property
    @wait_or_exit_before
    def vaults(self) -> List[Vault]:
        return list(self._vaults.values())

    @property
    @wait_or_exit_before
    def experiments(self) -> List[Vault]:
        return list(self._experiments.values())

    @property
    @wait_or_exit_before
    def staking_pools(self) -> Dict:
        return self._staking_pools

    @wait_or_exit_before
    def __repr__(self) -> str:
        return f"<Registry chain={chain.id} releases={len(self.releases)} vaults={len(self.vaults)} experiments={len(self.experiments)}>"

    @wait_or_exit_after
    def load_vaults(self):
        if not self._thread._started.is_set():
            self._thread.start()

    @sentry_catch_all
    def watch_events(self):
        start = time.time()
        sleep_time = 300
        from_block = None
        height = chain.height
        while True:
            logs = get_logs_asap([str(addr) for addr in self.registries], None, from_block=from_block, to_block=height)
            self.process_events(decode_logs(logs))
            self._filter_vaults()
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded v2 registry in %.3fs", time.time() - start)
            if not self._watch_events_forever:
                return
            time.sleep(sleep_time)

            # set vars for next loop
            from_block = height + 1
            height = chain.height
            if height < from_block:
                raise NodeNotSynced(f"No new blocks in the past {sleep_time/60} minutes.")

    def process_events(self, events):
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

            if event.name == "StakingPoolAdded":
                self._staking_pools[event["token"]] = event["staking_pool"]


    def vault_from_event(self, event):
        return Vault(
            vault=patch_contract(Contract.from_abi("Vault", event["vault"], self.releases[event["api_version"]].abi), dank_w3),
            token=event["token"],
            api_version=event["api_version"],
            registry=self,
            watch_events_forever=self._watch_events_forever,
        )

    def load_strategies(self):
        # stagger loading strategies to not run out of connections in the pool
        vaults = self.vaults + self.experiments
        Parallel(1, "threading")(delayed(vault.load_strategies)() for vault in vaults)

    def load_harvests(self):
        vaults = self.vaults + self.experiments
        Parallel(1, "threading")(delayed(vault.load_harvests)() for vault in vaults)

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
        vaults = self.vaults + self.experiments
        if block:
            blocks = await asyncio.gather(*[contract_creation_block_async(str(vault.vault)) for vault in vaults])
            vaults = [vault for vault, deploy_block in zip(vaults, blocks) if deploy_block <= block]
        # fixes edge case: a vault is not necessarily initialized on creation
        activations = await fetch_multicall_async(*[[vault.vault, 'activation'] for vault in vaults], block=block)
        return [vault for vault, activation in zip(vaults, activations) if activation]

    def _filter_vaults(self):
        logger.debug('filtering vaults')
        if chain.id in DEPRECATED_VAULTS:
            for vault in DEPRECATED_VAULTS[chain.id]:
                self._remove_vault(vault)
        logger.debug('vaults filtered')

    def _remove_vault(self, address):
        self._vaults.pop(address, None)
        self._experiments.pop(address, None)
        self.tags.pop(address, None)
        logger.debug('removed %s', address)
