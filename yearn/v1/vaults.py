import logging
from dataclasses import dataclass
from typing import Optional

from brownie import Contract, ZERO_ADDRESS, interface, web3
from brownie.network.contract import InterfaceContainer
from joblib import Parallel, delayed

from yearn import constants, curve, apy
from yearn.utils import contract_creation_block
from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.prices.curve import is_curve_lp_token
from yearn.apy.common import ApySamples
from pprint import pprint

logger = logging.getLogger(__name__)


@dataclass
class VaultV1:
    vault: InterfaceContainer
    controller: InterfaceContainer
    token: interface.ERC20
    strategy: str
    is_wrapped: bool
    is_delegated: bool
    # the rest is populated in post init
    name: Optional[str] = None
    decimals: Optional[int] = None

    def __post_init__(self):
        self.vault = Contract(self.vault)
        self.controller = Contract(self.controller)
        self.strategy = Contract(self.strategy)
        self.token = Contract(self.token)
        if str(self.vault) not in constants.VAULT_ALIASES:
            logger.warning("no vault alias for %s, reading from vault.sybmol()", self.vault)
        self.name = constants.VAULT_ALIASES.get(str(self.vault), self.vault.symbol())
        self.decimals = self.vault.decimals()  # vaults inherit decimals from token
        self.scale = 10 ** self.decimals

    def get_price(self, block=None):
        if self.name == "aLINK":
            return magic.get_price(self.vault.underlying(), block=block)
        return magic.get_price(self.token, block=block)

    def get_strategy(self, block=None):
        if self.name in ["aLINK", "LINK"]:
            return self.strategy
        strategy = self.controller.strategies(self.token, block_identifier=block)
        return Contract(strategy)

    def describe(self, block=None):
        info = {}
        strategy = self.strategy
        if block is not None:
            strategy = self.get_strategy(block=block)

        # attrs are fetches as multicall and populate info
        attrs = {
            "vault balance": [self.vault, "balance"],
            "vault total": [self.vault, "totalSupply"],
            "strategy balance": [strategy, "balanceOf"],
            "share price": [self.vault, "getPricePerFullShare"],
        }

        # some of the oldest vaults don't implement these methods
        if hasattr(self.vault, "available"):
            attrs["available"] = [self.vault, "available"]

        if hasattr(self.vault, "min") and hasattr(self.vault, "max"):
            attrs["min"] = [self.vault, "min"]
            attrs["max"] = [self.vault, "max"]

        # new curve voter proxy vaults
        if hasattr(strategy, "proxy"):
            vote_proxy, gauge = fetch_multicall(
                [strategy, "voter"],  # voter is static, can pin
                [strategy, "gauge"],  # gauge is static per strategy, can cache
                block=block,
            )
            vote_proxy = interface.CurveYCRVVoter(vote_proxy)
            gauge = Contract(gauge)
            info.update(curve.calculate_boost(gauge, vote_proxy, block=block))
            info.update(curve.calculate_apy(gauge, self.token, block=block))
            attrs["earned"] = [gauge, "claimable_tokens", vote_proxy]  # / scale

        if hasattr(strategy, "earned"):
            attrs["lifetime earned"] = [strategy, "earned"]  # /scale

        if strategy._name == "StrategyYFIGovernance":
            ygov = interface.YearnGovernance(strategy.gov())
            attrs["earned"] = [ygov, "earned", strategy]
            attrs["reward rate"] = [ygov, "rewardRate"]
            attrs["ygov balance"] = [ygov, "balanceOf", strategy]
            attrs["ygov total"] = [ygov, "totalSupply"]

        # fetch attrs as multicall
        results = fetch_multicall(*attrs.values(), block=block)
        scale_overrides = {"share price": 1e18}
        for name, attr in zip(attrs, results):
            if attr is not None:
                info[name] = attr / scale_overrides.get(name, self.scale)
            else:
                logger.warning("attr %s rekt %s", name, attr)

        # some additional post-processing
        if "min" in info:
            info["strategy buffer"] = info.pop("min") / info.pop("max")

        if "token price" not in info:
            info["token price"] = self.get_price(block=block)

        info["tvl"] = info["vault balance"] * info["token price"]

        return info

    def apy(self, samples: ApySamples):
        if is_curve_lp_token(self.token.address):
            return apy.curve.simple(self, samples)
        else:
            return apy.v1.simple(self, samples)