import asyncio
import os
import re
import logging
from datetime import datetime, timezone, timedelta

import eth_retry

from brownie import chain
from pprint import pformat

from y import Contract, magic, Network
from y.time import get_block_timestamp, closest_block_after_timestamp
from y.contracts import contract_creation_block_async
from y.exceptions import PriceError, yPriceMagicError

from yearn.apy.common import (Apy, ApyFees,
                              ApySamples, SECONDS_PER_YEAR, SECONDS_PER_WEEK, SharePricePoint, calculate_roi, get_samples)
from yearn.common import Tvl
from yearn.events import decode_logs, get_logs_asap
from yearn.utils import Singleton
from yearn.prices.constants import weth
from yearn.debug import Debug

logger = logging.getLogger("yearn.yeth")

if chain.id == Network.Mainnet:
    YETH_POOL = Contract("0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63")
    STAKING_CONTRACT = Contract("0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4") # st-yETH
    YETH_TOKEN = Contract("0x1BED97CBC3c24A4fb5C069C6E311a967386131f7") # yETH

class StYETH:
    def __init__(self, block=None):
        self.name = "st-yETH"
        self.address = str(STAKING_CONTRACT)
        self.lsts = []
        # TODO load assets via events
        for i in range(YETH_POOL.num_assets(block_identifier=block)):
            address = YETH_POOL.assets(i, block_identifier=block)
            lst = YETHLST(address, i)
            self.lsts.append(lst)

    @property
    def decimals(self):
        return 18

    @property
    def symbol(self):
        return 'st-yETH'


    async def _get_supply_price(self, block=None):
        data = YETH_POOL.vb_prod_sum(block_identifier=block)
        supply = data[1] / 1e18
        try:
            price = await magic.get_price(YETH_TOKEN, block=block, sync=False)
        except yPriceMagicError as e:
            if not isinstance(e.exception, PriceError):
                raise e
            price = None

        return supply, price


    @eth_retry.auto_retry
    async def apy(self, samples: ApySamples) -> Apy:
        block = samples.now
        now = get_block_timestamp(block)
        seconds_til_eow = SECONDS_PER_WEEK - now % SECONDS_PER_WEEK

        data = STAKING_CONTRACT.get_amounts(block_identifier=block)
        streaming = data[1]
        unlocked = data[2]
        apr = streaming * SECONDS_PER_YEAR / seconds_til_eow / unlocked
        performance_fee = STAKING_CONTRACT.performance_fee_rate(block_identifier=block) / 1e4

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
        try:
            pool_supply = YETH_POOL.supply(block_identifier=block)
            total_assets = STAKING_CONTRACT.totalAssets(block_identifier=block)
            boost = total_assets / pool_supply
        except Exception as e:
            logger.error(e)
            boost = 0

        if block:
            block_timestamp = get_block_timestamp(block)
            samples = get_samples(datetime.fromtimestamp(block_timestamp))
        else:
            samples = get_samples()

        apy = await self.apy(samples)
        return {
            'address': self.address,
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
    def __init__(self, address, asset_id):
        self.asset_id = asset_id
        self.address = address
        self.lst = Contract(address)
        self.name = self._sanitize(self.lst.name())
        self.rate_provider = Contract(YETH_POOL.rate_providers(asset_id))

    @property
    def symbol(self):
        return self.lst.symbol()

    @property
    def decimals(self):
        return 18

    def _sanitize(self, name):
        return re.sub(r"([\d]+)\.[\d]*", r"\1", name)

    def _get_lst_data(self, block=None):
        virtual_balance = YETH_POOL.virtual_balance(self.asset_id, block_identifier=block) / 1e18
        weights = YETH_POOL.weight(self.asset_id, block_identifier=block)
        weight = weights[0] / 1e18
        target = weights[1] / 1e18
        rate, _ = self._get_rate([block])
        return {
          "virtual_balance": virtual_balance,
          "weight": weight,
          "target": target,
          "rate": rate / 1e18
        }

    def _get_rate(self, blocks, idx=0):
        block = blocks[idx]
        try:
            return self.rate_provider.rate(self.address, block_identifier=block), block
        except ValueError as ve:
            logger.error(ve)
            idx += 1
            if idx == len(blocks):
                return 1e18, block
            else:
                return self._get_rate(blocks, idx)

    @eth_retry.auto_retry
    async def apy(self, samples: ApySamples) -> Apy:
        now_rate, now_block = self._get_rate([samples.now])
        previous_rate, previous_block = self._get_rate([samples.week_ago, samples.day_ago])

        now_point = SharePricePoint(now_block, now_rate)
        previous_point = SharePricePoint(previous_block, previous_rate)
        apy = calculate_roi(now_point, previous_point)

        return Apy("yETH", gross_apr=apy, net_apy=apy, fees=ApyFees())

    @eth_retry.auto_retry
    async def tvl(self, block=None) -> Tvl:
        data = self._get_lst_data(block=block)
        tvl = data["virtual_balance"] * data["rate"]
        return Tvl(data["virtual_balance"], data["rate"], tvl)

    async def describe(self, block=None):
        weth_price = await magic.get_price(weth, block=block, sync=False)
        data = self._get_lst_data(block=block)

        if block:
            block_timestamp = get_block_timestamp(block)
            samples = get_samples(datetime.fromtimestamp(block_timestamp))
        else:
            samples = get_samples()

        apy = await self.apy(samples)

        registry = Registry()
        swap_volumes = registry.swap_volumes

        return {
            'address': self.address,
            'weth_price': weth_price,
            'virtual_balance': data["virtual_balance"],
            'rate': data["rate"],
            'weight': data["weight"],
            'target': data["target"],
            'net_apy': apy.net_apy,
            'gross_apr': apy.gross_apr,
            'volume_in_eth': swap_volumes['volume_in_eth'][self.asset_id],
            'volume_out_eth': swap_volumes['volume_out_eth'][self.asset_id],
            'volume_in_usd': swap_volumes['volume_in_usd'][self.asset_id],
            'volume_out_usd': swap_volumes['volume_out_usd'][self.asset_id]
        }

    async def total_value_at(self, block=None):
        data = self._get_lst_data(block=block)
        tvl = data["virtual_balance"] * data["rate"]
        return tvl


class Registry(metaclass = Singleton):
    def __init__(self) -> None:
        self.st_yeth = StYETH()
        self.swap_volumes = {}
        self.resolution = os.environ.get('RESOLUTION', '1h') # Default: 1 hour

    async def _get_swap_volumes(self, from_block, to_block):
        logs = get_logs_asap([str(YETH_POOL)], None, from_block=from_block, to_block=to_block)
        events = decode_logs(logs)

        num_assets = YETH_POOL.num_assets(block_identifier=from_block)
        volume_in_eth = [0] * num_assets
        volume_out_eth = [0] * num_assets
        volume_in_usd = [0] * num_assets
        volume_out_usd = [0] * num_assets

        rates = []
        for i in range(num_assets):
            lst = self.st_yeth.lsts[i]
            rate, _ = lst._get_rate([from_block])
            rates.append(rate / 1e18)

        for e in events:
            if e.name == "Swap":
                asset_in = e["asset_in"]
                asset_out = e["asset_out"]
                amount_in = e["amount_in"] / 1e18
                amount_out = e["amount_out"] / 1e18
                volume_in_eth[asset_in] += amount_in * rates[asset_in]
                volume_out_eth[asset_out] += amount_out * rates[asset_out]

        weth_price = await magic.get_price(weth, block=from_block, sync=False)
        for i, value in enumerate(volume_in_eth):
            volume_in_usd[i] = value * weth_price

        for i, value in enumerate(volume_out_eth):
            volume_out_usd[i] = value * weth_price

        return {
          "volume_in_eth": volume_in_eth,
          "volume_out_eth": volume_out_eth,
          "volume_in_usd": volume_in_usd,
          "volume_out_usd": volume_out_usd
        }

    async def describe(self, block=None):
        to_block = chain.height
        now_time = datetime.today()
        if block:
            to_block = block
            block_timestamp = get_block_timestamp(block)
            now_time = datetime.fromtimestamp(block_timestamp)

        from_block = self._get_from_block(now_time)

        self.st_yeth = StYETH(to_block)
        self.swap_volumes = await self._get_swap_volumes(from_block, to_block)
        products = await self.active_products_at(block)
        data = await asyncio.gather(*[product.describe(block=block) for product in products])
        return {product.name: desc for product, desc in zip(products, data)}

    async def total_value_at(self, block=None):
        products = await self.active_products_at(block)
        tvls = await asyncio.gather(*[product.total_value_at(block=block) for product in products])
        return {product.name: tvl for product, tvl in zip(products, tvls)}

    async def active_products_at(self, block=None):
        products = [self.st_yeth] + self.st_yeth.lsts
        if block:
            blocks = await asyncio.gather(*[contract_creation_block_async(str(product.address)) for product in products])
            products = [product for product, deploy_block in zip(products, blocks) if deploy_block <= block]
        return products

    def _get_from_block(self, now_time):
        from_time = None
        match self.resolution:
            case "1d":
                from_time = (now_time - timedelta(days=1)).timestamp()
            case "1h":
                from_time = (now_time - timedelta(hours=1)).timestamp()
            case "30m":
                from_time = (now_time - timedelta(minutes=30)).timestamp()
            case "15m":
                from_time = (now_time - timedelta(minutes=15)).timestamp()
            case "5m":
                from_time = (now_time - timedelta(minutes=5)).timestamp()
            case "1m":
                from_time = (now_time - timedelta(minutes=1)).timestamp()
            case "30s":
                from_time = (now_time - timedelta(seconds=30)).timestamp()
            case "15s":
                from_time = (now_time - timedelta(seconds=15)).timestamp()
            case _:
                raise Exception(f"Invalid resolution {self.resolution} specified!")

        return closest_block_after_timestamp(int(from_time), True)
