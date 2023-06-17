import asyncio
import functools
import os
import re
from asyncio import current_task, iscoroutinefunction
from concurrent.futures import ThreadPoolExecutor
from threading import current_thread
from typing import Awaitable, Callable

import sentry_sdk.client
from brownie import chain, web3
from sentry_sdk import Hub, capture_message, init, push_scope, set_tag, utils
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration
from y.networks import Network

SENTRY_DSN = os.getenv('SENTRY_DSN')

sentry_executor = ThreadPoolExecutor(1)

def before_send(event, hint):
    # custom event parsing goes here
    # NOTE: We can't add our tag logic here because this is not called in the same thread where the Exception occurred.
    return event

def set_custom_tags():
    set_tag("chain_id", chain.id)
    set_tag("network", Network(chain.id).name())
    set_tag("web3_client_version", web3.clientVersion)
    set_tag("provider", _clean_creds_from_uri(web3.provider.endpoint_uri))

def setup_sentry():
    # NOTE: This ensures that even when sentry internals capture an exception, the extra tags are set.    
    #sentry_sdk.hub.Hub._capture_exception_old = Hub.capture_exception
    #sentry_sdk.hub.Hub.capture_exception = _capture_exception_redefined
    #sentry_sdk.hub.GLOBAL_HUB = sentry_sdk.hub.Hub()
    #sentry_sdk.hub._local.set(sentry_sdk.hub.GLOBAL_HUB)
    sentry_sdk.Client._capture_event_old = sentry_sdk.Client.capture_event
    sentry_sdk.Client.capture_event = _capture_event_redefined
    
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
            integrations=[
                AsyncioIntegration(),
                # NOTE: Threads are still used in some places in the codebase, we'll keep this for now.
                ThreadingIntegration(propagate_hub=True)
            ],
            ignore_errors=[
                KeyboardInterrupt, # these can be created when exiting a script with ctrl+c or when an exception is raised in a child thread. Ignore in both cases
            ]
        )
        set_custom_tags()

async def capture_exception(e: Exception) -> None:
    """An async version of sentry_sdk.capture_exception to eliminate blocking."""
    try:
        await asyncio.get_event_loop().run_in_executor(
            sentry_executor,
            _capture_exception_async_helper, 
            e,
            task=str(current_task()),
            thread=current_thread().name,
        )
    except RuntimeError:
        # This happens when you're using PYTHONASYNCIODEBUG=True, don't worry about it. Prod will not be impacted.
        pass
    
def _clean_creds_from_uri(endpoint: str) -> str:
    """
    This will help devs more easily debug provider-specific issues without revealing anybody's creds.
    """
    return re.sub(pattern=r"(https?:\/\/)[^@]+@(.+)", repl=r"\2", string=endpoint)

def _capture_event_redefined(
        self,
        event: "sentry_sdk.client.Event",
        hint: "sentry_sdk.client.Hint",  # type: Hint
        scope: sentry_sdk.Scope,  # type: Optional[Scope]
    ):
    """We monkey patch sentry_sdk.capture_exception to capture additional info."""
    if scope is None:
        with push_scope() as scope:
            _tag_scope(scope)
            self._capture_event_old(event, hint, scope)
    else:
        _tag_scope(scope)
        #Hub.current._capture_exception_old(e)
        self._capture_event_old(event, hint, scope)
        
def _tag_scope(scope: sentry_sdk.Scope) -> None:
    # Sets some last-minute tags to the current scope before capturing an event.
    if "task" not in scope._tags:
        try:
            task = current_task()
        except RuntimeError as e:
            if str(e) != "no running event loop":
                raise e
            task = None
        scope.set_tag("task", str(task))
    if "thread" not in scope._tags:
        scope.set_tag("thread", current_thread().name)
    
def _capture_exception_async_helper(e: Exception, thread: str, task: str) -> None:
    # NOTE: We have to get the task and thread info outside of this fn because this fn is called inside of a ThreadPoolExecutor.
    with push_scope() as scope:
        scope.set_tag("task", task)
        scope.set_tag("thread", thread)
        sentry_sdk.capture_exception(e)
        #Hub.current._capture_exception_old(e)

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
