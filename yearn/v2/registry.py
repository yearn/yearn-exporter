from threading import Thread
import logging
from joblib import Parallel, delayed

from brownie import Contract, chain
from yearn.events import create_filter, decode_logs
from yearn.v2.vaults import VaultV2

logger = logging.getLogger(__name__)


class Registry:
    def __init__(self):
        self.releases = {}  # api_version => template
        self.vaults = {}  # address => VaultV2
        self.experiments = {}  # address => VaultV2
        self.governance = None
        self.tags = {}

        # latest registry is always available at v2.registry.ychad.eth
        # but we also track older registries to pull experiments
        self.addresses = [
            "0xE15461B18EE31b7379019Dc523231C57d1Cbc18c",  # v2.0
            "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",  # v2.1
        ]

        # recover registry state from events
        self.log_filter = create_filter(self.addresses)
        self.events = decode_logs(self.log_filter.get_new_entries())
        self.process_events(self.events)

        # keep watching for new changes
        # self.thread = Thread(target=self.watch_events)
        # self.thread.start()

    def __repr__(self) -> str:
        return f"<Registry releases={len(self.releases)} vaults={len(self.vaults)} experiments={len(self.experiments)}>"

    def process_events(self, events):
        for event in events:
            logger.debug("%s %s %s", event.address, event.name, dict(event))
            if event.name == "NewGovernance":
                self.governance = event["governance"]

            if event.name == "NewRelease":
                self.releases[event["api_version"]] = Contract(event["template"])

            if event.name == "NewVault":
                # experiment was endorsed
                if event["vault"] in self.experiments:
                    vault = self.experiments.pop(event["vault"])
                    vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                    self.vaults[event["vault"]] = vault
                # we already know this vault from another registry
                elif event["vault"] not in self.vaults:
                    vault = self.vault_from_event(event)
                    vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                    self.vaults[event["vault"]] = vault
                    logger.debug("new vault %s", vault)

            if event.name == "NewExperimentalVault":
                vault = self.vault_from_event(event)
                vault.name = f"{vault.vault.symbol()} {event['api_version']} {event['vault'][:8]}"
                self.experiments[event["vault"]] = vault
                logger.debug("new experiment %s", vault)

            if event.name == "VaultTagged":
                self.tags[event["vault"]] = event["tag"]

    def vault_from_event(self, event):
        return VaultV2(
            vault=Contract.from_abi("Vault", event["vault"], self.releases[event["api_version"]].abi),
            token=event["token"],
            api_version=event["api_version"],
            registry=self,
        )

    def watch_events(self):
        for block in chain.new_blocks(poll_interval=60):
            logs = self.log_filter.get_new_entries()
            self.process_events(decode_logs(logs))

    def load_strategies(self):
        vaults = list(self.vaults.values()) + list(self.experiments.values())
        Parallel(8, 'threading')(
            delayed(vault.load_strategies)()
            for vault in vaults
        )

    def describe_vaults(self):
        vaults = list(self.vaults.values()) + list(self.experiments.values())
        results = Parallel(8, 'threading')(
            delayed(vault.describe)()
            for vault in vaults
        )
        return {vault.name: result for vault, result in zip(vaults, results)}
