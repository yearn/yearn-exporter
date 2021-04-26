from collections import defaultdict
from dataclasses import dataclass

from brownie import Contract
from brownie.network.contract import InterfaceContainer
from joblib import Parallel, delayed

from yearn.utils import contract_creation_block
from yearn.multicall2 import multicall_matrix
from yearn.prices import magic


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
    def __init__(self):
        ironbank = Contract("0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB")
        markets = [Contract(market) for market in ironbank.getAllMarkets()]
        cdata = multicall_matrix(markets, ["symbol", "underlying", "decimals"])
        underlying = [Contract(cdata[x]["underlying"]) for x in markets]
        data = multicall_matrix(underlying, ["symbol", "decimals"])
        self.vaults = [
            IronbankMarket(
                cdata[market]["symbol"],
                market,
                data[token]["symbol"],
                token,
                cdata[market]["decimals"],
                data[token]["decimals"],
            )
            for market, token in zip(markets, underlying)
        ]

    def __repr__(self):
        return f"<IronBank markets={len(self.vaults)}>"

    def describe(self, block=None):
        markets = self.active_vaults_at(block)
        blocks_per_year = 365 * 86400 / 15
        contracts = [m.vault for m in markets]
        results = multicall_matrix(
            contracts,
            [
                "exchangeRateCurrent",
                "getCash",
                "totalBorrows",
                "totalSupply",
                "totalReserves",
                "supplyRatePerBlock",
                "borrowRatePerBlock",
            ],
            block=block,
        )
        prices = Parallel(8, "threading")(
            delayed(magic.get_price)(market.underlying, block=block) for market in markets
        )
        output = defaultdict(dict)
        for m, price in zip(markets, prices):
            res = results[m.vault]
            exchange_rate = res["exchangeRateCurrent"] * 10 ** (m.cdecimals - m.decimals - 18)
            for attr in ["getCash", "totalBorrows", "totalReserves"]:
                res[attr] /= 10 ** m.decimals

            tvl = (res["getCash"] + res["totalBorrows"] - res["totalReserves"]) * price
            supplied = res["getCash"] + res["totalBorrows"] - res["totalReserves"]
            ratio = res["totalBorrows"] / supplied if supplied != 0 else None

            output[m.name] = {
                "total supply": res["totalSupply"] / 10 ** m.cdecimals,
                "total cash": res["getCash"],
                "total supplied": supplied,
                "total borrows": res["totalBorrows"],
                "total reserves": res["totalReserves"],
                "exchange rate": exchange_rate,
                "token price": price * exchange_rate,
                "underlying price": price,
                "supply apy": res["supplyRatePerBlock"] / 1e18 * blocks_per_year,
                "borrow apy": res["borrowRatePerBlock"] / 1e18 * blocks_per_year,
                "utilization": ratio,
                "tvl": tvl,
            }

        return dict(output)

    def total_value_at(self, block=None):
        markets = self.active_vaults_at(block)
        data = multicall_matrix(
            [market.vault for market in markets],
            ["getCash", "totalBorrows", "totalReserves", "totalSupply"],
            block=block,
        )
        prices = Parallel(8, "threading")(delayed(magic.get_price)(market.vault, block=block) for market in markets)
        results = [data[market.vault] for market in markets]
        return {
            # market.name: (res["getCash"] + res["totalBorrows"] - res["totalReserves"]) / 10 ** market.decimals * price
            market.name: res["totalSupply"] / 10 ** market.cdecimals * price
            for market, price, res in zip(markets, prices, results)
        }

    def active_vaults_at(self, block=None):
        if block is None:
            return self.vaults
        return [market for market in self.vaults if contract_creation_block(str(market.vault)) < block]
