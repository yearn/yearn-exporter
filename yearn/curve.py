from brownie import Contract, interface, chain

from yearn.multicall2 import fetch_multicall
from yearn.prices import magic
from yearn.prices.curve import curve


@property
def crv():
    if chain.id == 1:
        return Contract("0xD533a949740bb3306d119CC777fa900bA034cd52")


@property
def voting_escrow():
    if chain.id == 1:
        return interface.CurveVotingEscrow("0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2")

@property
def gauge_controller():
    if chain.id == 1:
        return interface.CurveGaugeController("0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB")


@property
def registry():
    if chain.id == 1:
        return interface.CurveRegistry("0x7D86446dDb609eD0F5f8684AcF30380a356b2B4c")


def calculate_boost(gauge, addr, block=None):
    results = fetch_multicall(
        [gauge, "balanceOf", addr],
        [gauge, "totalSupply"],
        [gauge, "working_balances", addr],
        [gauge, "working_supply"],
        [voting_escrow, "balanceOf", addr],
        [voting_escrow, "totalSupply"],
        block=block,
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


def calculate_apy(gauge, lp_token, block=None):
    crv_price = magic.get_price(crv)
    pool = Contract(curve.get_pool(lp_token))
    results = fetch_multicall(
        [gauge, "working_supply"],
        [gauge_controller, "gauge_relative_weight", gauge],
        [gauge, "inflation_rate"],
        [pool, "get_virtual_price"],
        block=block,
    )
    results = [x / 1e18 for x in results]
    working_supply, relative_weight, inflation_rate, virtual_price = results
    token_price = magic.get_price(lp_token, block=block)
    try:
        rate = (inflation_rate * relative_weight * 86400 * 365 / working_supply * 0.4) / token_price
    except ZeroDivisionError:
        rate = 0

    return {
        "crv price": crv_price,
        "relative weight": relative_weight,
        "inflation rate": inflation_rate,
        "virtual price": virtual_price,
        "crv reward rate": rate,
        "crv apy": rate * crv_price,
        "token price": token_price,
    }
