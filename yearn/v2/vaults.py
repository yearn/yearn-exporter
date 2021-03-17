from threading import Thread

from brownie.network.contract import Contract
from eth_utils import encode_hex, event_abi_to_log_topic
from yearn.prices import magic
from yearn.events import create_filter, decode_logs
from yearn.mutlicall import fetch_multicall
from yearn.utils import safe_views
from yearn.v2.strategies import Strategy

VAULT_VIEWS_SCALED = [
    "totalAssets",
    "maxAvailableShares",
    "pricePerShare",
    "debtOutstanding",
    "creditAvailable",
    "expectedReturn",
    "totalSupply",
    "availableDepositLimit",
    "depositLimit",
    "totalDebt",
    "debtLimit",
    "lockedProfit",
    "lockedProfitDegration",
]

# we are only interested in strategy-related events
STRATEGY_EVENTS = [
    "StrategyAdded",
    "StrategyMigrated",
    "StrategyRevoked",
    # "StrategyReported",
]


class VaultV2:
    def __init__(self, vault, api_version, token=None, registry=None):
        self.strategies = {}
        self.revoked_strategies = {}
        self.vault = vault
        if token is None:
            token = vault.token()
        self.token = Contract(token)
        self.registry = registry
        self.scale = 10 ** self.vault.decimals()
        # mutlicall-safe views with 0 inputs and numeric output.
        self._views = safe_views(self.vault.abi)

    def __repr__(self):
        name = getattr(self, "name", self.vault.symbol())
        strategies = ", ".join(f'{strategy}' for strategy in self.strategies.values())
        return f'<Vault {self.vault} name="{name}" token={self.token} strategies=[{strategies}]>'

    @property
    def is_endorsed(self):
        assert self.registry, "Vault not from Registry"
        return str(self.vault) in self.registry.vaults

    @property
    def is_experiment(self):
        assert self.registry, "Vault not from Registry"
        return self.registry and str(self.vault) in self.registry.experiments

    def load_strategies(self):
        topics = [
            [
                encode_hex(event_abi_to_log_topic(event))
                for event in self.vault.abi
                if event["type"] == "event" and event["name"] in STRATEGY_EVENTS
            ]
        ]
        self.log_filter = create_filter(str(self.vault), topics=topics)
        logs = self.log_filter.get_new_entries()
        events = decode_logs(logs)

        for event in events:
            if event.name == "StrategyAdded":
                self.strategies[event["strategy"]] = Strategy(event["strategy"], self)
            elif event.name == "StrategyRevoked":
                self.revoked_strategies[event["strategy"]] = self.strategies.pop(
                    event["strategy"], Strategy(event["strategy"], self)
                )
            elif event.name == "StrategyMigrated":
                self.revoked_strategies[event["oldVersion"]] = self.strategies.pop(
                    event["oldVersion"], Strategy(event["oldVersion"], self)
                )
                self.strategies[event["newVersion"]] = Strategy(event["newVersion"], self)

    def describe(self):
        try:
            results = fetch_multicall(
                *[[self.vault, view] for view in self._views],
            )
            info = dict(zip(self._views, results))
            for name in info:
                if name in VAULT_VIEWS_SCALED:
                    info[name] /= self.scale
            info["strategies"] = {}
        except ValueError as e:
            info = {"strategies": {}}
        
        for strategy in self.strategies.values():
            info["strategies"][strategy.name] = strategy.describe()

        info["token price"] = magic.get_price(self.token)
        if "totalAssets" in info:
            info["tvl"] = info["token price"] * info["totalAssets"]

        return info
