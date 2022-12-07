
from yearn.treasury.buckets import get_token_bucket

def test_get_token_bucket():
    new_bal_pool = "0x2F4eb100552ef93840d5aDC30560E5513DFfFACb"
    assert get_token_bucket(new_bal_pool)
