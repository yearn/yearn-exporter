from sentry_sdk import Hub, init, set_tag, capture_message
from sentry_sdk.integrations.threading import ThreadingIntegration
import os

environment = os.getenv('ENV', 'DEVELOPMENT')

def before_send(event, hint):
    # custom event parsing goes here
    return event

def setup_sentry():
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        init(
            sentry_dsn,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production.
            traces_sample_rate=1.0,
            environment=environment,
            before_send=before_send,
            debug=False,
            integrations=[ThreadingIntegration(propagate_hub=True)]
        )
