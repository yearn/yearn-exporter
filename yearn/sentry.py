import os

from brownie import chain
from sentry_sdk import Hub, capture_message, init, set_tag
from sentry_sdk.integrations.threading import ThreadingIntegration

from yearn.networks import Network

environment = os.getenv('ENV', 'DEVELOPMENT')

def before_send(event, hint):
    # custom event parsing goes here
    return event

def set_custom_tags():
    set_tag("chain_id", chain.id)
    set_tag("network_label", Network.label(chain.id))


def setup_sentry():
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        init(
            sentry_dsn,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production.
            traces_sample_rate=1.0,
            shutdown_timeout=5,
            environment=environment,
            before_send=before_send,
            debug=False,
            integrations=[ThreadingIntegration(propagate_hub=True)],
            ignore_errors=[
                KeyboardInterrupt, # these can be created when exiting a script with ctrl+c or when an exception is raised in a child thread. Ignore in both cases
            ]
        )
        set_custom_tags()
