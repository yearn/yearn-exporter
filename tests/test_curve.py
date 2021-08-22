from brownie import Contract, ZERO_ADDRESS
from yearn.constants import YEARN_ADDRESSES_PROVIDER, CURVE_ADDRESSES_PROVIDER

def test_curve_pools():
    from yearn.prices.curve import get_pool
    from yearn.prices.magic import get_price
    
    addresses_provider_yearn = Contract(YEARN_ADDRESSES_PROVIDER)
    addresses_provider_curve = Contract(CURVE_ADDRESSES_PROVIDER)
    curve_registry = Contract(addresses_provider_curve.get_registry())
    curve_addresses_helper = Contract(addresses_provider_yearn.addressById("HELPER_CURVE_ADDRESSES"))
    lps_addresses = curve_addresses_helper.lpsAddresses()
    pools_addresses = curve_addresses_helper.poolsAddresses()
    
    # Make sure helper utility accounts for every pool (regular pools, metapools, crypto pools)
    number_of_pools = curve_registry.pool_count()
    assert len(lps_addresses) == number_of_pools
    assert len(pools_addresses) == number_of_pools

    # Make sure lp -> pool addresses line up with expectations
    for (idx, lp_address) in enumerate(lps_addresses):
        pool_address = get_pool(lp_address)
        assert pool_address is not None
        assert pool_address != ZERO_ADDRESS
        assert pool_address == pools_addresses[idx]

    # Make sure no pool prices are zero
    for lp_address in lps_addresses:
        lp = Contract(lp_address)
        price = get_price(lp_address)
        print(f"{lp_address}: {price} ({lp.symbol()})")
        assert price > 0
