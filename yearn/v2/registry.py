import logging
import threading
import time
from typing import List

from brownie import Contract, chain, web3
from joblib import Parallel, delayed
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set
from yearn.events import create_filter, decode_logs, get_logs_asap
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.utils import contract_creation_block, contract, get_start_block
from yearn.singleton import Singleton
from yearn.v2.vaults import Vault
from yearn.networks import Network
from yearn.exceptions import UnsupportedNetwork
from yearn.decorators import sentry_catch_all, wait_or_exit_before, wait_or_exit_after

logger = logging.getLogger(__name__)


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
        return [Contract(event['newAddress']) for event in events]

    @property
    @wait_or_exit_before
    def vaults(self) -> List[Vault]:
        return list(self._vaults.values())

    @property
    @wait_or_exit_before
    def experiments(self) -> List[Vault]:
        return list(self._experiments.values())

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
        self.log_filter = create_filter([str(addr) for addr in self.registries])
        logs = self.log_filter.get_all_entries()
        while True:
            self.process_events(decode_logs(logs))
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded v2 registry in %.3fs", time.time() - start)
            if not self._watch_events_forever:
                return
            time.sleep(300)

            # read new logs at end of loop
            logs = self.log_filter.get_new_entries()

    def process_events(self, events):
        for event in events:
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
                self.tags[event["vault"]] = event["tag"]

    def vault_from_event(self, event):
        return Vault(
            vault=Contract.from_abi("Vault", event["vault"], self.releases[event["api_version"]].abi),
            token=event["token"],
            api_version=event["api_version"],
            registry=self,
            watch_events_forever=self._watch_events_forever,
        )

    def load_strategies(self):
        # stagger loading strategies to not run out of connections in the pool
        vaults = self.vaults + self.experiments
        Parallel(8, "threading")(delayed(vault.load_strategies)() for vault in vaults)

    def load_harvests(self):
        vaults = self.vaults + self.experiments
        Parallel(8, "threading")(delayed(vault.load_harvests)() for vault in vaults)

    def describe(self, block=None):
        vaults = self.active_vaults_at(block)
        results = Parallel(8, "threading")(delayed(vault.describe)(block=block) for vault in vaults)
        return {vault.name: result for vault, result in zip(vaults, results)}

    def total_value_at(self, block=None):
        vaults = self.active_vaults_at(block)
        prices = Parallel(8, "threading")(delayed(magic.get_price)(str(vault.token), block=block) for vault in vaults)
        results = fetch_multicall(*[[vault.vault, "totalAssets"] for vault in vaults], block=block)
        return {vault.name: assets * price / vault.scale for vault, assets, price in zip(vaults, results, prices)}

    def active_vaults_at(self, block=None):
        vaults = self.vaults + self.experiments
        if block:
            vaults = [vault for vault in vaults if contract_creation_block(str(vault.vault)) <= block]
        # fixes edge case: a vault is not necessarily initialized on creation
        activations = fetch_multicall(*[[vault.vault, 'activation'] for vault in vaults], block=block)
        return [vault for vault, activation in zip(vaults, activations) if activation]

    def wallets(self, block=None):
        return set(vault.wallets(block) for vault in self.active_vaults_at(block))
