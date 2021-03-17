from threading import Thread

from brownie import Contract, chain
from yearn.events import create_filter, decode_logs
from yearn.v2.vaults import VaultV2


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
        self.thread = Thread(target=self.watch_events)
        self.thread.start()

    def __repr__(self) -> str:
        return f"<Registry releases={len(self.releases)} vaults={len(self.vaults)} experiments={len(self.experiments)}>"

    def process_events(self, events):
        for event in events:
            if event.name == "NewGovernance":
                self.governance = event["governance"]

            if event.name == "NewRelease":
                self.releases[event["api_version"]] = Contract(event["template"])

            if event.name in ["NewVault", "NewExperimentalVault"]:
                # if the vault was endorsed, we already have it as an experiment
                vault = self.experiments.pop(
                    event["vault"],
                    VaultV2(
                        vault=Contract.from_abi("Vault", event["vault"], self.releases[event["api_version"]].abi),
                        token=event["token"],
                        registry=self,
                    ),
                )
                if event.name == "NewExperimentalVault":
                    # there can be several experiments of the same version
                    # disambiguate them by appending a part of the address
                    vault.name = f"{vault.vault.symbol()} {event['api_version']} {event['vault'][:10]}"
                    self.experiments[event["vault"]] = vault
                if event.name == "NewVault":
                    vault.name = f"{vault.vault.symbol()} {event['api_version']}"
                    self.vaults[event["vault"]] = vault

            if event.name == "VaultTagged":
                self.tags[event["vault"]] = event["tag"]

    def watch_events(self):
        for block in chain.new_blocks(poll_interval=60):
            logs = self.log_filter.get_new_entries()
            self.process_events(decode_logs(logs))
