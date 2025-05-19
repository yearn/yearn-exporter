import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from a_sync import cgather
from async_lru import alru_cache
from async_property import async_cached_property
from brownie import ZERO_ADDRESS, interface
from brownie.network.contract import InterfaceContainer
from y import Address, Contract, magic, get_price
from y._decorators import stuck_coro_debugger
from y.exceptions import PriceError, yPriceMagicError

from yearn import constants
from yearn.common import Tvl
from yearn.multicall2 import fetch_multicall_async
from yearn.prices.curve import curve
from yearn.v1 import constants

if TYPE_CHECKING:
    from yearn.apy.common import ApySamples

logger = logging.getLogger(__name__)


@alru_cache
async def get_vote_proxy(vote_proxy: Address) -> Contract:
    vote_proxy = interface.CurveYCRVVoter(vote_proxy)
    return await Contract.from_abi("CurveYCRVVoter", vote_proxy.address, vote_proxy.abi, sync=False)

@alru_cache
async def get_ygov(strategy: Contract) -> Contract:
    ygov = interface.YearnGovernance(await strategy.gov)
    return await Contract.from_abi("YearnGovernance", ygov.address, ygov.abi, sync=False)

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

    async def get_price(self, block=None):
        if self.name == "aLINK":
            underlying = await self.vault.underlying.coroutine()
            return await get_price(underlying, block=block, sync=False)
        return await get_price(self.token, block=block, sync=False)

    @stuck_coro_debugger
    async def get_strategy(self, block=None):
        if self.name in ["aLINK", "LINK"] or block is None:
            return self.strategy
        
        controller = await self.get_controller(block)
        strategy = await controller.strategies.coroutine(self.token, block_identifier=block)
        if strategy != ZERO_ADDRESS:
            return Contract(strategy)

    @stuck_coro_debugger
    async def get_controller(self, block=None):
        if block is None:
            return self.controller
        return await Contract.coroutine(await self.vault.controller.coroutine(block_identifier=block))

    @async_cached_property
    @stuck_coro_debugger
    async def is_curve_vault(self):
        return await magic.curve.get_pool(str(self.token)) is not None

    @stuck_coro_debugger
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
        if await self.is_curve_vault and hasattr(strategy, "proxy"):
            vote_proxy, gauge = await fetch_multicall_async(
                (
                    [strategy, "voter"],  # TODO: voter is static, can pin
                    [strategy, "gauge"],  # TODO: gauge is static per strategy, can cache
                ),
                block=block,
            )
            # guard historical queries where there are no vote_proxy and gauge
            # for block <= 10635293 (2020-08-11)
            if vote_proxy and gauge:
                vote_proxy, gauge = await cgather(
                    get_vote_proxy(vote_proxy),
                    Contract.coroutine(gauge),
                )
                boost, _apy = await cgather(
                    curve.calculate_boost(gauge, vote_proxy, block=block),
                    curve.calculate_apy(gauge, self.token, block=block),
                )
                info |= boost
                info |= _apy
                attrs["earned"] = [gauge, "claimable_tokens", vote_proxy]  # / scale

        if hasattr(strategy, "earned"):
            attrs["lifetime earned"] = [strategy, "earned"]  # /scale

        if strategy._name == "StrategyYFIGovernance":
            ygov = await get_ygov(strategy)
            attrs["earned"] = [ygov, "earned", strategy]
            attrs["reward rate"] = [ygov, "rewardRate"]
            attrs["ygov balance"] = [ygov, "balanceOf", strategy]
            attrs["ygov total"] = [ygov, "totalSupply"]

        # fetch attrs as multicall
        results = await fetch_multicall_async(attrs.values(), block=block)
        scale_overrides = {"share price": 1e18}
        self_scale = self.scale
        for name, attr in zip(attrs, results):
            if attr is not None:
                info[name] = attr / scale_overrides.get(name, self_scale)
            else:
                logger.warning("attr %s rekt %s", name, attr)

        # some additional post-processing
        if "min" in info:
            info["strategy buffer"] = info.pop("min") / info.pop("max")

        if "token price" not in info:
            info["token price"] = float(await self.get_price(block=block)) if info["vault total"] > 0 else 0

        info["tvl"] = info["vault balance"] * float(info["token price"])

        return info

    @stuck_coro_debugger
    async def apy(self, samples: "ApySamples"):
        from yearn import apy
        from yearn.prices.curve import curve
        if await magic.curve.get_pool(self.token.address):
            return await apy.curve.simple(self, samples)
        else:
            return await apy.v1.simple(self, samples)

    @stuck_coro_debugger
    async def tvl(self, block=None):
        total_assets = await self.vault.balance.coroutine(block_identifier=block)
        try:
            price = float(await get_price(self.token, block=block, sync=False))
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = None
        tvl = total_assets * price / 10 ** await self.vault.decimals.coroutine(block_identifier=block) if price else None
        return Tvl(total_assets, price, tvl) 


from queue import SimpleQueue
from collections import deque

class unzip:
    def __init__(self, iterable):
        self.iterable = iterable
        self.queues = []
        for val in next(iter(iterable)):
            queue = deque()
            queue.append(val)
            self.queues.append(queue)
    
    def __iter__(self):
        iterator = iter(self.iterable)
        queues = self.queues
        iterating = True
        
        def _iterator(i):
            my_queue = queues[i]
            other_queues = {_i: queue for _i, queue in enumerate(queues) if _i != i}
            nonlocal iterating
            while iterating:
                while my_queue:
                    yield my_queue.popleft()
                try:
                    tup = next(iterator)
                except StopIteration:
                    iterating = False
                    return
                yield tup[i]
                for _i, queue in other_queues.items():
                    queue.append(tup[_i])
            while my_queue:
                yield my_queue.popleft()
        
        return tuple(map(_iterator, range(len(queues))))
