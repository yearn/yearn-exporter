import asyncio
import os
import logging
from datetime import datetime, timezone

import eth_retry
from pprint import pformat

from y import Contract, magic
from y.time import get_block_timestamp
from y.contracts import contract_creation_block_async
from y.exceptions import PriceError, yPriceMagicError

from yearn.apy.common import (Apy, ApyBlocks, ApyError, ApyFees, ApyPoints,
                              ApySamples, SECONDS_PER_YEAR, SECONDS_PER_WEEK, SharePricePoint, calculate_roi, get_samples)
from yearn.common import Tvl
from yearn.utils import Singleton
from yearn.prices.constants import weth
from yearn.debug import Debug

logger = logging.getLogger("yearn.yeth")

YETH_POOL = Contract("0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63")

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
        data = YETH_POOL.vb_prod_sum(block_identifier=block)
        supply = data[1]
        try:
            price = await magic.get_price(self.token, block=block, sync=False)
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = None

        return supply / 10**self.token.decimals(), price


    @eth_retry.auto_retry
    async def apy(self, samples: ApySamples) -> Apy:
        block = samples.now
        now = get_block_timestamp(block)
        seconds_til_eow = SECONDS_PER_WEEK - now % SECONDS_PER_WEEK

        data = self.vault.get_amounts(block_identifier=block)
        streaming = data[1]
        unlocked = data[2]
        apr = streaming * SECONDS_PER_YEAR / seconds_til_eow / unlocked
        performance_fee = self.vault.performance_fee_rate(block_identifier=block) / 1e4

        if os.getenv("DEBUG", None):
            logger.info(pformat(Debug().collect_variables(locals())))

        return Apy("yETH", gross_apr=apr, net_apy=apr, fees=ApyFees(performance=performance_fee))


    @eth_retry.auto_retry
    async def tvl(self, block=None) -> Tvl:
        supply, price = await self._get_supply_price(block=block)
        tvl = supply * price if price else None

        return Tvl(supply, price, tvl)


    async def describe(self, block=None):
        supply, price = await self._get_supply_price(block=block)
        pool_supply = YETH_POOL.supply(block_identifier=block)
        total_assets = self.vault.totalAssets(block_identifier=block)
        boost = 1 - pool_supply / total_assets

        if block:
            block_timestamp = get_block_timestamp(block)
            samples = get_samples(datetime.fromtimestamp(block_timestamp))
        else:
            samples = get_samples()

        apy = await self.apy(samples)
        return {
            'address': str(self.vault),
            'totalSupply': supply,
            'token price': price,
            'tvl': supply * price,
            'net_apy': apy.net_apy,
            'gross_apr': apy.gross_apr,
            'boost': boost
        }


    async def total_value_at(self, block=None):
        supply, price = await self._get_supply_price(block=block)
        return supply * price


class YETHLST():
    def __init__(self, address, idx):
        self.id = idx
        self.vault = Contract(address)
        self.name = self.vault.name()
        self.token = self.vault
        self.rate_provider = Contract("0x4e322aeAf355dFf8fb9Fd5D18F3D87667E8f8316")

    @property
    def strategies(self):
        return []

    @property
    def symbol(self):
        return self.vault.symbol()

    async def _get_supply_price(self, block=None):
        supply = YETH_POOL.virtual_balance(self.id, block_identifier=block)
        weth_price = await magic.get_price(weth, block=block, sync=False)
        price = weth_price * self.rate_provider.rate(str(self.vault), block_identifier=block) / 10**self.vault.decimals()

        return supply / 10**self.vault.decimals(), price

    @eth_retry.auto_retry
    async def apy(self, samples: ApySamples) -> Apy:
        now_rate = self.rate_provider.rate(str(self.vault), block_identifier=samples.now) / 10**self.vault.decimals()
        week_ago_rate = self.rate_provider.rate(str(self.vault), block_identifier=samples.week_ago) / 10**self.vault.decimals()
        now_point = SharePricePoint(samples.now, now_rate)
        week_ago_point = SharePricePoint(samples.week_ago, week_ago_rate)
        apy = calculate_roi(now_point, week_ago_point)

        return Apy("yETH", gross_apr=apy, net_apy=apy, fees=ApyFees())

    @eth_retry.auto_retry
    async def tvl(self, block=None) -> Tvl:
        supply, price = await self._get_supply_price(block)
        tvl = supply * price
        return Tvl(supply, price, tvl)

    async def describe(self, block=None):
        supply, price = await self._get_supply_price(block)
        if block:
            block_timestamp = get_block_timestamp(block)
            samples = get_samples(datetime.fromtimestamp(block_timestamp))
        else:
            samples = get_samples()

        apy = await self.apy(samples)

        return {
            'address': str(self.vault),
            'totalSupply': supply,
            'token price': price,
            'tvl': supply * price,
            'net_apy': apy.net_apy,
            'gross_apr': apy.gross_apr
        }

    async def total_value_at(self, block=None):
        supply, price = await self._get_supply_price(block)
        return supply * price


class Registry(metaclass = Singleton):
    def __init__(self) -> None:
        self.vaults = [StYETH()]
        for i in range(YETH_POOL.num_assets()):
            address = YETH_POOL.assets(i)
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
