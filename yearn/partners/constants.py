from bisect import bisect_right

OPEX_COST = 0.35

TIERS = {
    0: 0,
    1_000_000: 0.10,
    5_000_000: 0.15,
    10_000_000: 0.20,
    50_000_000: 0.25,
    100_000_000: 0.30,
    200_000_000: 0.35,
    400_000_000: 0.40,
    700_000_000: 0.45,
    1_000_000_000: 0.5,
}


def get_tier(amount):
    keys = sorted(TIERS)
    index = bisect_right(keys, amount) - 1
    return TIERS[keys[index]]
