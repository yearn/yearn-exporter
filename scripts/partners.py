import sentry_sdk
from yearn.partners.partners import partners
from yearn.partners.snapshot import process_partners

sentry_sdk.set_tag('script','partners')


def main():
    process_partners(partners)
