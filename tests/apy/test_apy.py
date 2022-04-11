from datetime import datetime
import pytest
from pytest_bdd import scenario, given, then, parsers
from yearn.apy.curve.simple import simple
from yearn.apy.common import get_samples
from yearn.v2.vaults import Vault as VaultV2

@scenario("curve_simple_apy.feature", "Calculating curve simple")
def test_curve_simple_apy():
    pass

@given(parsers.parse("I set the date to '{date}'"), target_fixture="apy_samples")
def given_set_date(date):
    now_time = datetime.strptime(date, "%Y-%m-%d")
    return get_samples(now_time)

@given(parsers.parse("I calculate the APY for the vault {address}"), target_fixture="apy_result")
def given_start_calculation(apy_samples, address):
    vault = VaultV2.from_address(address)
    return simple(vault, apy_samples)

@then(parsers.parse("the type should be {type}"))
def should_match_type(apy_result, type):
    assert apy_result.type == type

@then(parsers.parse("the gross_apr should be {gross_apr:f}"))
def should_match_gross_apr(apy_result, gross_apr):
    assert pytest.approx(apy_result.gross_apr, rel=1e-2) == gross_apr

@then(parsers.parse("the net_apy should be {net_apy:f}"))
def should_match_net_apy(apy_result, net_apy):
    assert pytest.approx(apy_result.net_apy, rel=1e-2) == net_apy
