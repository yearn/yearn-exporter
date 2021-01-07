from brownie import interface

from yearn import constants
from yearn import uniswap


crv = interface.ERC20('0xD533a949740bb3306d119CC777fa900bA034cd52')
voting_escrow = interface.CurveVotingEscrow('0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2')


def calculate_boost(gauge, addr):
    gauge_balance = gauge.balanceOf(addr) / 1e18
    gauge_total = gauge.totalSupply() / 1e18
    working_balance = gauge.working_balances(addr) / 1e18
    working_supply = gauge.working_supply() / 1e18
    vecrv_balance = voting_escrow.balanceOf(addr) / 1e18
    vecrv_total = voting_escrow.totalSupply() / 1e18
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
        'gauge balance': gauge_balance,
        'gauge total': gauge_total,
        'vecrv balance': vecrv_balance,
        'vecrv total': vecrv_total,
        'working balance': working_balance,
        'working total': working_supply,
        'boost': boost,
        'max boost': max_boost_possible,
        'min vecrv': min_vecrv,
    }


def calculate_apy(gauge, swap):
    crv_price = uniswap.price_router(crv, uniswap.usdc)
    gauge_controller = interface.CurveGaugeController(gauge.controller())
    working_supply = gauge.working_supply() / 1e18
    relative_weight = gauge_controller.gauge_relative_weight(gauge) / 1e18
    inflation_rate = gauge.inflation_rate() / 1e18
    virtual_price = swap.get_virtual_price() / 1e18
    base_price = 1
    if str(swap) in constants.CURVE_BTC_SWAPS:
        base_price *= uniswap.price_router(uniswap.wbtc, uniswap.usdc)

    try:
        rate = (inflation_rate * relative_weight * 86400 * 365 / working_supply * 0.4) / (virtual_price * base_price)
    except ZeroDivisionError:
        rate = 0

    return {
        'crv price': crv_price,
        'relative weight': relative_weight,
        'inflation rate': inflation_rate,
        'virtual price': virtual_price,
        'base price': base_price,
        'crv reward rate': rate,
        'crv apy': rate * crv_price,
        'token price': base_price * virtual_price,
    }
