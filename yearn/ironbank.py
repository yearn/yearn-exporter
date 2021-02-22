from collections import defaultdict
from dataclasses import dataclass

from brownie import Contract, interface
from brownie.network.contract import InterfaceContainer

from yearn import uniswap
from yearn.mutlicall import multicall_matrix


@dataclass
class IronbankMarket:
    name: str
    ctoken: InterfaceContainer
    token_name: str
    underlying: InterfaceContainer
    cdecimals: int
    decimals: int


def load_ironbank():
    ironbank = Contract("0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB")
    markets = [interface.CErc20(market) for market in ironbank.getAllMarkets()]
    cdata = multicall_matrix(markets, ["symbol", "underlying", "decimals"])
    underlying = [Contract(cdata[x]["underlying"]) for x in markets]
    data = multicall_matrix(underlying, ["symbol", "decimals"])
    return [
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


def describe_ironbank(markets):
    blocks_per_year = 365 * 86400 / 15
    contracts = [m.ctoken for m in markets]
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
    )
    output = defaultdict(dict)
    for m in markets:
        res = results[m.ctoken]
        price = uniswap.token_price(m.underlying)
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
