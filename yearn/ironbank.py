import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import List

from brownie import chain
from brownie.network.contract import InterfaceContainer
from cachetools.func import ttl_cache
from y import Contract, Network
from y.prices import magic

from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import multicall_matrix, multicall_matrix_async
from yearn.prices.compound import get_fantom_ironbank
from yearn.typing import Address

logger = logging.getLogger(__name__)

addresses = {
    Network.Mainnet: '0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB',
    Network.Fantom: get_fantom_ironbank,
    Network.Arbitrum: '0xbadaC56c9aca307079e8B8FC699987AAc89813ee',
    Network.Optimism: '0xE0B57FEEd45e7D908f2d0DaCd26F113Cf26715BF',
}


@dataclass
class IronbankMarket:
    name: str
    vault: InterfaceContainer
    token_name: str
    underlying: InterfaceContainer
    cdecimals: int
    decimals: int

    @property
    def token(self):
        return self.underlying


class Registry:
    def __init__(self, exclude_ib_tvl: bool = True):
        if chain.id not in addresses:
            raise UnsupportedNetwork('iron bank is not supported on this network')
        self.exclude_ib_tvl = exclude_ib_tvl
        self._vaults: List[IronbankMarket] = []

    def __repr__(self):
        return f"<IronBank markets={len(self.vaults)}>"
    
    def __len__(self) -> int:
        return len(self.vaults)
    
    @property
    def vaults(self):
        if len(self.__all_markets) > len(self._vaults):
            self.load_new_markets()
        return self._vaults
    
    def load_new_markets(self) -> List[IronbankMarket]:
        new_markets = self.__all_markets[len(self._vaults):]
        new_markets = [Contract(market) for market in new_markets]
        cdata = multicall_matrix(new_markets, ["symbol", "underlying", "decimals"])
        underlying = [Contract(cdata[x]["underlying"]) for x in new_markets]
        data = multicall_matrix(underlying, ["symbol", "decimals"])
        new_markets = [
            IronbankMarket(
                cdata[market]["symbol"],
                market,
                data[token]["symbol"],
                token,
                cdata[market]["decimals"],
                data[token]["decimals"],
            )
            for market, token
            in zip(new_markets, underlying)
        ]
        self._vaults.extend(new_markets)
        logger.info('loaded %d ironbank markets', len(new_markets))
        return new_markets

    @cached_property
    def ironbank(self):
        addr = addresses[chain.id]
        return Contract(addr) if isinstance(addr, str) else addr()

    async def describe(self, block=None):
        markets = await self.active_vaults_at(block)
        blocks_per_year = 365 * 86400 / 15
        contracts = [m.vault for m in markets]
        methods = [
            "exchangeRateCurrent",
            "getCash",
            "totalBorrows",
            "totalSupply",
            "totalReserves",
            "supplyRatePerBlock",
            "borrowRatePerBlock",
        ]
        results, prices = await asyncio.gather(
            multicall_matrix_async(contracts, methods, block=block),
            asyncio.gather(*[magic.get_price(market.underlying, block=block, sync=False) for market in markets]),
        )
        output = defaultdict(dict)
        for m, price in zip(markets, prices):
            res = results[m.vault]
            exchange_rate = res["exchangeRateCurrent"] * 10 ** (m.cdecimals - m.decimals - 18)
            for attr in ["getCash", "totalBorrows", "totalReserves"]:
                res[attr] /= 10 ** m.decimals

            tvl = (res["getCash"] + res["totalBorrows"] - res["totalReserves"]) * float(price)
            supplied = res["getCash"] + res["totalBorrows"] - res["totalReserves"]
            ratio = res["totalBorrows"] / supplied if supplied != 0 else None

            output[m.name] = {
                "total supply": res["totalSupply"] / 10 ** m.cdecimals,
                "total cash": res["getCash"],
                "total supplied": supplied,
                "total borrows": res["totalBorrows"],
                "total reserves": res["totalReserves"],
                "exchange rate": exchange_rate,
                "token price": float(price) * exchange_rate,
                "underlying price": price,
                "supply apy": res["supplyRatePerBlock"] / 1e18 * blocks_per_year,
                "borrow apy": res["borrowRatePerBlock"] / 1e18 * blocks_per_year,
                "utilization": ratio,
                "tvl": tvl,
                "address": m.vault.address,
                "version": "ib",
            }

        return dict(output)

    async def total_value_at(self, block=None):
        markets = await self.active_vaults_at(block)
        data_coro = multicall_matrix_async(
            [market.vault for market in markets],
            ["getCash", "totalBorrows", "totalReserves", "totalSupply"],
            block=block,
        )
        data, prices = await asyncio.gather(
            data_coro,
            asyncio.gather(*[magic.get_price(market.vault, block=block, sync=False) for market in markets]),
        )
        results = [data[market.vault] for market in markets]
        return {
            # market.name: (res["getCash"] + res["totalBorrows"] - res["totalReserves"]) / 10 ** market.decimals * price
            market.name: res["totalSupply"] / 10 ** market.cdecimals * price
            for market, price, res in zip(markets, prices, results)
        }

    async def active_vaults_at(self, block=None):
        if block is None:
            return self.vaults

        try:
            active_markets_at_block = await self.ironbank.getAllMarkets.coroutine(block_identifier=block)
            return [market for market in self.vaults if market.vault in active_markets_at_block]
        except ValueError:
            return []
    
    @property
    @ttl_cache(ttl=300)
    def __all_markets(self) -> List[Address]:
        return self.ironbank.getAllMarkets()
