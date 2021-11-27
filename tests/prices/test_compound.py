from yearn.prices.compound import compound

def test_compound_pricing():
    for comp in compound.compounds:
        print(comp)
        for market in comp.markets:
            print(market)
            if market.token == '0x892B14321a4FCba80669aE30Bd0cd99a7ECF6aC0':
                continue  # creth is broken
            print(market.name)
            print(f'undecimals = {market.under_decimals}')
            print(f' cdecimals = {market.cdecimals}')

            print(f'  exchange = {market.get_exchange_rate()}')
            print(f'underlying = {market.get_underlying_price()}')
            print(f'     price = {compound.get_price(market.token)}')


def test_compound_cap():
    for comp in compound.compounds:
        print(comp.name)
        total = 0
        for token in comp.markets:
            if token.token == '0x892B14321a4FCba80669aE30Bd0cd99a7ECF6aC0':
                continue  # creth is broken
            
            price = comp.get_price(token.token)
            supply = token.ctoken.totalSupply() / 10 ** token.cdecimals
            print(f'  {token.name} {supply:,.0f} x {price:,.2f} = {supply * price:,.0f}')
            total += supply * price

        print(f'{comp.name} = {total:,.0f}')
