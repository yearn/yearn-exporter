import asyncio
import math
from time import time
from typing import TYPE_CHECKING, Tuple

import eth_retry
import requests
from brownie import chain
from y import ERC20, Contract, magic
from y.contracts import contract_creation_block_async
from y.exceptions import PriceError, yPriceMagicError

from yearn import constants
from yearn.apy.common import (Apy, ApyBlocks, ApyError, ApyFees, ApyPoints,
                              ApySamples)
from yearn.common import Tvl
from yearn.prices.curve import curve
from yearn.utils import Singleton

if TYPE_CHECKING:
    from yearn.apy.common import Apy, ApySamples


class YveCRVJar(metaclass = Singleton):
    def __init__(self):
        self.id = "yvecrv-eth"
        self.name = "pickling SushiSwap LP Token"
        self.vault = Contract("0xbD17B1ce622d73bD438b9E658acA5996dc394b0d")
        self.token = Contract("0x5Eff6d166D66BacBC1BF52E2C54dD391AE6b1f48")

    @property
    def strategies(self):
        return []

    @property
    def decimals(self):
        return 18

    @property
    def symbol(self):
        return 'pSLP'

    @eth_retry.auto_retry
    async def apy(self, _: ApySamples) -> Apy:
        try:
            data = requests.get("https://api.pickle.finance/prod/protocol/pools").json()
        except requests.exceptions.SSLError as e:
            raise ApyError("yvecrv-jar", "ssl error") from e
        yvboost_eth_pool  = [pool for pool in data if pool["identifier"] == "yvboost-eth"][0]
        apy = yvboost_eth_pool["apy"]  / 100.
        points = ApyPoints(apy, apy, apy)
        block = chain.height
        inception_block = await contract_creation_block_async(str(self.vault))
        blocks = ApyBlocks(block, block, block, inception_block)
        return Apy("yvecrv-jar", apy, apy, ApyFees(), points=points, blocks=blocks)

    @eth_retry.auto_retry
    async def tvl(self, block=None) -> Tvl:
        try:
            data = requests.get("https://api.pickle.finance/prod/protocol/value").json()
        except requests.exceptions.SSLError as e:
            return Tvl(tvl=None)
        tvl = data[self.id]
        return Tvl(tvl=tvl)

class Backscratcher(metaclass = Singleton):
    def __init__(self):
        self.name = "yveCRV"
        self.vault = Contract("0xc5bDdf9843308380375a611c18B50Fb9341f502A")
        self.token = Contract("0xD533a949740bb3306d119CC777fa900bA034cd52")
        self.proxy = Contract("0xF147b8125d2ef93FB6965Db97D6746952a133934")
    
    async def _locked(self, block=None) -> Tuple[float,float]:
        crv_locked, crv_price = await asyncio.gather(
            curve.voting_escrow.balanceOf["address"].coroutine(self.proxy, block_identifier=block),
            magic.get_price(constants.CRV, block=block, sync=False),
        )
        crv_locked /= 1e18
        return crv_locked, crv_price

    async def describe(self, block=None):
        crv_locked, crv_price = await self._locked(block=block)
        return {
            'totalSupply': crv_locked,
            'token price': crv_price,
            'tvl': crv_locked * float(crv_price),
        }

    async def total_value_at(self, block=None):
        crv_locked, crv_price = await self._locked(block=block)
        return crv_locked * crv_price

    @property
    def strategies(self):
        return []

    async def apy(self, _: "ApySamples") -> "Apy":
        curve_3_pool, curve_reward_distribution, curve_voting_escrow = await asyncio.gather(
            Contract.coroutine("0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"),
            Contract.coroutine("0xA464e6DCda8AC41e03616F95f4BC98a13b8922Dc"),
            Contract.coroutine("0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2"),
        )
        
        week = 7 * 86400
        epoch = math.floor(time() / week) * week - week
        voter = "0xF147b8125d2ef93FB6965Db97D6746952a133934"
        crv_price, yvecrv_price, total_vecrv, yearn_vecrv, vault_supply, tokens_per_week, virtual_price = await asyncio.gather(
            magic.get_price("0xD533a949740bb3306d119CC777fa900bA034cd52", sync=False),
            magic.get_price("0xc5bDdf9843308380375a611c18B50Fb9341f502A", sync=False),
            curve_voting_escrow.totalSupply.coroutine(),
            curve_voting_escrow.balanceOf.coroutine(voter),
            self.vault.totalSupply.coroutine(),
            curve_reward_distribution.tokens_per_week.coroutine(epoch),
            curve_3_pool.get_virtual_price.coroutine(),
        )

        tokens_per_week /= 1e18
        virtual_price /= 1e18
        # although we call this APY, this is actually APR since there is no compounding
        apy = (tokens_per_week * virtual_price * 52) / ((total_vecrv / 1e18) * crv_price)
        vault_boost = (yearn_vecrv / vault_supply) * (crv_price / yvecrv_price)
        composite = {
            "currentBoost": vault_boost,
            "boostedApy": apy * vault_boost,
            "totalApy": apy * vault_boost,
            "poolApy": apy,
            "baseApy": apy,
        }
        return Apy("backscratcher", apy, apy, ApyFees(), composite=composite)

    async def tvl(self, block=None) -> Tvl:
        total_assets = await self.vault.totalSupply.coroutine(block_identifier=block)
        try:
            price = await magic.get_price(self.token, block=block, sync=False)
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = None
        tvl = total_assets * price / await ERC20(self.vault, asynchronous=True).scale if price else None
        return Tvl(total_assets, price, tvl)

class Ygov(metaclass = Singleton):
    def __init__(self):
        self.name = "yGov"
        self.vault = Contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")
        self.token = Contract("0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e")
    
    async def _locked(self, block=None):
        yfi_locked, yfi_price = await asyncio.gather(
            self.token.balanceOf.coroutine(self.vault, block_identifier=block),
            magic.get_price(str(self.token), block=block, sync=False)
        )
        yfi_locked /= 1e18
        return yfi_locked, yfi_price

    async def describe(self, block=None):
        yfi_locked, yfi_price = await self._locked(block=block)
        return {
            'totalAssets': yfi_locked,
            'token price': yfi_price,
            'tvl': yfi_locked * float(yfi_price),
        }

    async def total_value_at(self, block=None):
        yfi_locked, yfi_price = await self._locked(block=block)
        return yfi_locked * float(yfi_price)


class Registry(metaclass = Singleton):
    def __init__(self) -> None:
        self.vaults = [Backscratcher(), Ygov()]

    async def describe(self, block=None):
        # not supported yet
        vaults = await self.active_vaults_at(block)
        data = await asyncio.gather(*[vault.describe(block=block) for vault in vaults])
        return {vault.name: desc for vault, desc in zip(vaults, data)}

    async def total_value_at(self, block=None):
        vaults = await self.active_vaults_at(block)
        tvls = await asyncio.gather(*[vault.total_value_at(block=block) for vault in vaults])
        return {vault.name: tvl for vault, tvl in zip(vaults, tvls)}

    async def active_vaults_at(self, block=None):
        vaults = list(self.vaults)
        if block:
            blocks = await asyncio.gather(*[contract_creation_block_async(str(vault.vault)) for vault in self.vaults])
            vaults = [vault for vault, deploy_block in zip(self.vaults, blocks) if deploy_block <= block]
        return vaults
