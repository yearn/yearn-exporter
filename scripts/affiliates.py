from yearn.affiliates.partners import partners
from yearn.affiliates.snapshot import process_affiliates


def main():
    process_affiliates(partners)
