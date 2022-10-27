import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

from brownie import ZERO_ADDRESS, interface
from brownie.network.contract import InterfaceContainer
from dank_mids.brownie_patch import patch_contract
from multicall.utils import gather
from y.prices import magic
from y.utils.dank_mids import dank_w3
from yearn import apy, constants
from yearn.apy.common import ApySamples
from yearn.common import Tvl
from yearn.exceptions import PriceError
from yearn.multicall2 import fetch_multicall_async
from yearn.prices import magic
from yearn.prices.curve import curve
from yearn.utils import contract
from yearn.v1 import constants

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
        self.vault = contract(self.vault)
        self.controller = contract(self.controller)
        self.strategy = contract(self.strategy)
        self.token = contract(self.token)
        if str(self.vault) not in constants.VAULT_ALIASES:
            logger.warning("no vault alias for %s, reading from vault.sybmol()", self.vault)
        self.name = constants.VAULT_ALIASES.get(str(self.vault), self.vault.symbol())
        self.decimals = self.vault.decimals()  # vaults inherit decimals from token
        self.scale = 10 ** self.decimals

    async def get_price(self, block=None):
        if self.name == "aLINK":
            return await magic.get_price_async(self.vault.underlying.coroutine(), block=block)
        return await magic.get_price_async(self.token, block=block)

    async def get_strategy(self, block=None):
        if self.name in ["aLINK", "LINK"] or block is None:
            return self.strategy
        
        controller = await self.get_controller(block)
        strategy = controller.strategies(self.token, block_identifier=block)
        if strategy != ZERO_ADDRESS:
            return contract(strategy)

    async def get_controller(self, block=None):
        if block is None:
            return self.controller
        return contract(self.vault.controller(block_identifier=block))

    @cached_property
    def is_curve_vault(self):
        return curve.get_pool(str(self.token)) is not None

    async def describe(self, block=None):
        info = {}
        strategy = self.strategy
        if block is not None:
            strategy = await self.get_strategy(block=block)

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
        if self.is_curve_vault and hasattr(strategy, "proxy"):
            vote_proxy, gauge = await fetch_multicall_async(
                [strategy, "voter"],  # voter is static, can pin
                [strategy, "gauge"],  # gauge is static per strategy, can cache
                block=block,
            )
            # guard historical queries where there are no vote_proxy and gauge
            # for block <= 10635293 (2020-08-11)
            if vote_proxy and gauge:
                vote_proxy = patch_contract(interface.CurveYCRVVoter(vote_proxy), dank_w3)
                gauge = contract(gauge)
                #boost = await curve.calculate_boost(gauge, vote_proxy, block=block),
                #_apy = await curve.calculate_apy(gauge, self.token, block=block),
                boost, _apy = await gather([
                    curve.calculate_boost(gauge, vote_proxy, block=block),
                    curve.calculate_apy(gauge, self.token, block=block),
                ])
                info.update(boost)
                info.update(_apy)
                attrs["earned"] = [gauge, "claimable_tokens", vote_proxy]  # / scale

        if hasattr(strategy, "earned"):
            attrs["lifetime earned"] = [strategy, "earned"]  # /scale

        if strategy._name == "StrategyYFIGovernance":
            ygov = patch_contract(interface.YearnGovernance(await strategy.gov.coroutine()), dank_w3)
            attrs["earned"] = [ygov, "earned", strategy]
            attrs["reward rate"] = [ygov, "rewardRate"]
            attrs["ygov balance"] = [ygov, "balanceOf", strategy]
            attrs["ygov total"] = [ygov, "totalSupply"]

        # fetch attrs as multicall
        results = await fetch_multicall_async(*attrs.values(), block=block)
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
            info["token price"] = await self.get_price(block=block) if info["vault total"] > 0 else 0

        info["tvl"] = info["vault balance"] * info["token price"]
            
        return info

    def apy(self, samples: ApySamples):
        if curve.get_pool(self.token.address):
            return apy.curve.simple(self, samples)
        else:
            return apy.v1.simple(self, samples)

    def tvl(self, block=None):
        total_assets = self.vault.balance(block_identifier=block)
        try:
            price = magic.get_price(self.token, block=block)
        except PriceError:
            price = None
        tvl = total_assets * price / 10 ** self.vault.decimals(block_identifier=block) if price else None
        return Tvl(total_assets, price, tvl) 
