from brownie import ZERO_ADDRESS, interface, Contract
from cachetools import LRUCache, cached

from yearn.prices import magic
from yearn.mutlicall import fetch_multicall

crv = Contract("0xD533a949740bb3306d119CC777fa900bA034cd52")
voting_escrow = interface.CurveVotingEscrow("0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2")
gauge_controller = interface.CurveGaugeController("0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB")
registry = interface.CurveRegistry("0x7D86446dDb609eD0F5f8684AcF30380a356b2B4c")
underlying_coins = {}


@cached(LRUCache(1000))
def lp_to_pool(addr):
    return registry.get_pool_from_lp_token(addr)


@cached(LRUCache(1000))
def get_underlying(pool):
    return [coin for coin in registry.get_underlying_coins(pool) if coin != ZERO_ADDRESS]


def is_curve_lp_token(addr):
    return lp_to_pool(addr) != ZERO_ADDRESS


def get_base_price(pool_or_lp):
    # try to find pool for lp, otherwise assume pool
    pool = lp_to_pool(pool_or_lp)
    if pool == ZERO_ADDRESS:
        pool = pool_or_lp
    return magic.get_price(get_underlying(pool)[0])


def get_virtual_price(lp):
    return interface.CurveSwap(lp_to_pool(lp)).get_virtual_price() / 1e18


def calculate_boost(gauge, addr):
    results = fetch_multicall(
        [gauge, "balanceOf", addr],
        [gauge, "totalSupply"],
        [gauge, "working_balances", addr],
        [gauge, "working_supply"],
        [voting_escrow, "balanceOf", addr],
        [voting_escrow, "totalSupply"],
    )
    results = [x / 1e18 for x in results]
    gauge_balance, gauge_total, working_balance, working_supply, vecrv_balance, vecrv_total = results
    try:
        boost = working_balance / gauge_balance * 2.5
    except ZeroDivisionError:
        boost = 1

    min_vecrv = vecrv_total * gauge_balance / gauge_total
    lim = gauge_balance * 0.4 + gauge_total * min_vecrv / vecrv_total * 0.6
    lim = min(gauge_balance, lim)

    _working_supply = working_supply + lim - working_balance
    noboost_lim = gauge_balance * 0.4
    noboost_supply = working_supply + noboost_lim - working_balance
    try:
        max_boost_possible = (lim / _working_supply) / (noboost_lim / noboost_supply)
    except ZeroDivisionError:
        max_boost_possible = 1

    return {
        "gauge balance": gauge_balance,
        "gauge total": gauge_total,
        "vecrv balance": vecrv_balance,
        "vecrv total": vecrv_total,
        "working balance": working_balance,
        "working total": working_supply,
        "boost": boost,
        "max boost": max_boost_possible,
        "min vecrv": min_vecrv,
    }


def calculate_apy(gauge, swap):
    crv_price = magic.get_price(crv)
    results = fetch_multicall(
        [gauge, "working_supply"],
        [gauge_controller, "gauge_relative_weight", gauge],
        [gauge, "inflation_rate"],
        [swap, "get_virtual_price"],
    )
    results = [x / 1e18 for x in results]
    working_supply, relative_weight, inflation_rate, virtual_price = results
    base_price = get_base_price(swap)
    try:
        rate = (inflation_rate * relative_weight * 86400 * 365 / working_supply * 0.4) / (virtual_price * base_price)
    except ZeroDivisionError:
        rate = 0

    return {
        "crv price": crv_price,
        "relative weight": relative_weight,
        "inflation rate": inflation_rate,
        "virtual price": virtual_price,
        "base price": base_price,
        "crv reward rate": rate,
        "crv apy": rate * crv_price,
        "token price": base_price * virtual_price,
    }
