from typing import List

import pytest
from y import Network
from y.constants import CHAINID

from yearn.prices.compound import Compound, CompoundMarket, compound

comps: List[Compound] = [comp for comp in compound.compounds]
markets: List[CompoundMarket] = [market for comp in comps for market in comp.markets]

@pytest.mark.parametrize('market',markets)
def test_compound_pricing(market):
    if CHAINID == Network.Mainnet and str(market.ctoken) == '0x892B14321a4FCba80669aE30Bd0cd99a7ECF6aC0':
        pytest.skip('creth is broken.')

    print(market)
    print(market.name)
    print(f'undecimals = {market.under_decimals}')
    print(f' cdecimals = {market.cdecimals}')
    print(f'  exchange = {market.get_exchange_rate()}')
    print(f'underlying = {market.get_underlying_price()}')
    print(f'     price = {compound.get_price(str(market.ctoken))}')


@pytest.mark.parametrize('compound',comps)
def test_compound_cap(compound):
    print(compound.name)
    total = 0
    for market in compound.markets:
        if CHAINID == Network.Mainnet and str(market.ctoken) == '0x892B14321a4FCba80669aE30Bd0cd99a7ECF6aC0':
            continue  # creth is broken
        
        price = compound.get_price(market.token)
        if isinstance(price, list):
            price = price[0]

        supply = market.ctoken.totalSupply() / 10 ** market.cdecimals
        print(f'  {market.name} {supply:,.0f} x {price:,.2f} = {supply * price:,.0f}')
        total += supply * price

    print(f'{compound.name} = {total:,.0f}')
