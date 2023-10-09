import asyncio
import math
import os
from time import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Tuple

import eth_retry
import requests
from brownie import chain
from pprint import pformat

from y import Contract, magic
from y.contracts import contract_creation_block_async
from y.exceptions import PriceError, yPriceMagicError

from yearn.apy.common import (Apy, ApyBlocks, ApyError, ApyFees, ApyPoints,
                              ApySamples, SECONDS_PER_YEAR, SECONDS_PER_WEEK, SharePricePoint, calculate_roi, get_samples)
from yearn.common import Tvl
from yearn.utils import Singleton
from yearn.prices.constants import weth
from yearn.debug import Debug

if TYPE_CHECKING:
    from yearn.apy.common import Apy, ApySamples

class StYETH(metaclass = Singleton):
    def __init__(self):
        self.id = "st-yETH"
        self.name = "st-yETH"
        self.vault = Contract("0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4") # st-yETH
        self.token = Contract("0x1BED97CBC3c24A4fb5C069C6E311a967386131f7") # yETH

    @property
    def strategies(self):
        return []

    @property
    def decimals(self):
        return 18

    @property
    def symbol(self):
        return 'st-yETH'


    async def _get_supply_price(self, block=None):
        yeth_pool = Contract("0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63")
        data = yeth_pool.vb_prod_sum(block_identifier=block)
        supply = data[1]
        try:
            price = await magic.get_price(self.token, block=block, sync=False)
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = None

        return supply / 10**self.token.decimals(), price


    @eth_retry.auto_retry
    async def apy(self, _: ApySamples) -> Apy:
        now = datetime.utcnow()
        now = now.replace(tzinfo=timezone.utc)

        seconds_til_eow = SECONDS_PER_WEEK - int(now.timestamp()) % SECONDS_PER_WEEK

        data = self.vault.get_amounts()
        streaming = data[1]
        unlocked = data[2]
        apr = streaming * SECONDS_PER_YEAR / seconds_til_eow / unlocked

        if os.getenv("DEBUG", None):
            logger.info(pformat(Debug().collect_variables(locals())))

        # TODO fix fees
        return Apy("st-yeth", gross_apr=apr, net_apy=apr, fees=ApyFees())


    @eth_retry.auto_retry
    async def tvl(self, block=None) -> Tvl:
        supply, price = await self._get_supply_price(block=block)
        tvl = supply * price if price else None

        return Tvl(supply, price, tvl)


    async def describe(self, block=None):
        supply, price = await self._get_supply_price(block=block)

        apy = await self.apy(None)
        return {
            'type': 'yETH',
            'totalSupply': supply,
            'token price': price,
            'tvl': supply * price,
            'net_apy': apy.net_apy,
            'gross_apr': apy.gross_apr
        }


    async def total_value_at(self, block=None):
        supply, price = await asyncio.gather(
            self.token.balanceOf.coroutine(self.vault, block_identifier=block),
            magic.get_price(str(self.token), block=block, sync=False)
        )
        supply /= 1e18

        return supply * price


class YETHLST():
    def __init__(self, address, idx):
        self.id = idx
        self.vault = Contract(address)
        self.name = self.vault.name()
        self.token = self.vault

    @property
    def strategies(self):
        return []

    @property
    def symbol(self):
        return self.vault.symbol()

    async def _get_supply_price(self, block=None):
        yeth_pool = Contract("0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63")
        rate_provider = Contract("0x4e322aeAf355dFf8fb9Fd5D18F3D87667E8f8316")
        supply = yeth_pool.virtual_balance(self.id)
        weth_price = await magic.get_price(weth, block=block, sync=False)
        price = weth_price * rate_provider.rate(str(self.vault), block_identifier=block) / 10**self.vault.decimals()

        return supply / 10**self.vault.decimals(), price

    @eth_retry.auto_retry
    async def apy(self, samples: ApySamples) -> Apy:
        rate_provider = Contract("0x4e322aeAf355dFf8fb9Fd5D18F3D87667E8f8316")
        now_rate = rate_provider.rate(str(self.vault), block_identifier=samples.now) / 10**self.vault.decimals()
        week_ago_rate = rate_provider.rate(str(self.vault), block_identifier=samples.week_ago) / 10**self.vault.decimals()
        now_point = SharePricePoint(samples.now, now_rate)
        week_ago_point = SharePricePoint(samples.week_ago, week_ago_rate)
        apy = calculate_roi(now_point, week_ago_point)

        # TODO fix fees
        return Apy(self.name, gross_apr=apy, net_apy=apy, fees=ApyFees())

    @eth_retry.auto_retry
    async def tvl(self, block=None) -> Tvl:
        supply, price = await self._get_supply_price(block)
        tvl = supply * price
        return Tvl(supply, price, tvl)

    async def describe(self, block=None):
        supply, price = await self._get_supply_price(block)
        samples = get_samples()
        apy = await self.apy(samples)

        return {
            'type': 'yETH',
            'totalSupply': supply,
            'token price': price,
            'tvl': supply * price,
            'net_apy': apy.net_apy,
            'gross_apr': apy.gross_apr
        }

    async def total_value_at(self, block=None):
        supply, price = await self._get_supply_price(block)
        return supply * price


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
        from yearn.prices.curve import curve
        crv_locked, crv_price = await asyncio.gather(
            curve.voting_escrow.balanceOf["address"].coroutine(self.proxy, block_identifier=block),
            magic.get_price(curve.crv, block=block, sync=False),
        )
        crv_locked /= 1e18
        return crv_locked, crv_price

    async def describe(self, block=None):
        crv_locked, crv_price = await self._locked(block=block)
        return {
            'totalSupply': crv_locked,
            'token price': crv_price,
            'tvl': crv_locked * crv_price,
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
        tvl = total_assets * price / 10 ** await self.vault.decimals.coroutine(block_identifier=block) if price else None
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
            'tvl': yfi_locked * yfi_price,
        }

    async def total_value_at(self, block=None):
        yfi_locked, yfi_price = await self._locked(block=block)
        return yfi_locked * yfi_price


class Registry(metaclass = Singleton):
    def __init__(self) -> None:
        self.vaults = [Backscratcher(), Ygov(), StYETH()]
        yeth_pool = Contract("0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63")
        for i in range(yeth_pool.num_assets()):
            address = yeth_pool.assets(i)
            self.vaults.append(YETHLST(address, i))

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
