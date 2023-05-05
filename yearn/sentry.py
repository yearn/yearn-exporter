import asyncio
import functools
import os
import re
from asyncio import iscoroutinefunction
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable

from brownie import chain, web3
from sentry_sdk import Hub
from sentry_sdk import capture_exception as _capture_exception
from sentry_sdk import capture_message, init, set_tag, utils
from sentry_sdk.integrations.threading import ThreadingIntegration
from y.networks import Network

SENTRY_DSN = os.getenv('SENTRY_DSN')

sentry_executor = ThreadPoolExecutor(1)

def before_send(event, hint):
    # custom event parsing goes here
    return event

def set_custom_tags():
    set_tag("chain_id", chain.id)
    set_tag("network", Network(chain.id).name())
    set_tag("web3_client_version", web3.clientVersion)
    set_tag("provider", _clean_creds_from_uri(web3.provider.endpoint_uri))

def setup_sentry():
    if SENTRY_DSN:
        # give remote backtraces a bit more space
        utils.MAX_STRING_LENGTH = 8192
        init(
            SENTRY_DSN,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production.
            traces_sample_rate=1.0,
            shutdown_timeout=5,
            before_send=before_send,
            debug=False,
            integrations=[ThreadingIntegration(propagate_hub=True)],
            ignore_errors=[
                KeyboardInterrupt, # these can be created when exiting a script with ctrl+c or when an exception is raised in a child thread. Ignore in both cases
            ]
        )
        set_custom_tags()

def _clean_creds_from_uri(endpoint: str) -> str:
    """
    This will help devs more easily debug provider-specific issues without revealing anybody's creds.
    """
    return re.sub(pattern=r"(https?:\/\/)[^@]+@(.+)", repl=r"\2", string=endpoint)

async def capture_exception(e: Exception) -> None:
    try:
        await asyncio.get_event_loop().run_in_executor(sentry_executor, _capture_exception, e)
    except RuntimeError:
        # This happens when you're using PYTHONASYNCIODEBUG=True, don't worry about it. Prod will not be impacted.
        pass

def log_task_exceptions(func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
    """
    Decorate coroutine functions with log_task_exceptions if you will be submitting the coroutines to an asyncio event loop as task objects.
    """
    if not iscoroutinefunction(func):
        raise RuntimeError("log_task_exceptions decorator should only be applied to coroutine functions you will submit to the event loop as task objects.")

    @functools.wraps(func)
    async def wrap(*args, **kwargs) -> None:
        try:
            await func(*args, **kwargs)
        except Exception as e:
            if SENTRY_DSN is not None:
                await capture_exception(e)
            # Raise the exception so the user sees it on their logs.
            # Since it is raised inside of a task it will not impact behavior.            
            raise e
    return wrap
