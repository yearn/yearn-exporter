from brownie import interface

gauge_controller = interface.CurveGaugeController('0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB')
voting_escrow = interface.CurveVotingEscrow('0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2')


def caclulate_boost(gauge, addr):
    gauge_balance = gauge.balanceOf(addr) / 1e18
    gauge_total = gauge.totalSupply() / 1e18
    working_balance = gauge.working_balances(addr) / 1e18
    working_supply = gauge.working_supply() / 1e18
    vecrv_balance = voting_escrow.balanceOf(addr) / 1e18
    vecrv_total = voting_escrow.totalSupply() / 1e18
    boost = working_balance / gauge_balance * 2.5

    min_vecrv = vecrv_total * gauge_balance / gauge_total
    lim = gauge_balance * 0.4 + gauge_total * min_vecrv / vecrv_total * 0.6
    lim = min(gauge_balance, lim)

    _working_supply = working_supply + lim - working_balance
    noboost_lim = gauge_balance * 0.4
    noboost_supply = working_supply + noboost_lim - working_balance
    max_boost_possible = (lim / _working_supply) / (noboost_lim / noboost_supply)

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
