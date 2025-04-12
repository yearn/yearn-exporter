import _thread
import asyncio
import functools
import logging
import signal

import sentry_sdk

logger = logging.getLogger(__name__)

def sentry_catch_all(func):
    @functools.wraps(func)
    def wrap(self):
        try:
            func(self)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            self._has_exception = True
            self._exception = e
            self._done.set()
            raise
    return wrap


def wait_or_exit_before(func):
    @functools.wraps(func)
    async def wrap(self):
        task: asyncio.Task = self._task
        logger.debug("waiting for %s", self)
        while not self._done.is_set() and not task.done():
            await asyncio.sleep(10)
            logger.debug("%s not done", self)
        logger.debug("loading %s complete", self)
        if task.done() and (e := task.exception()):
            logger.debug('task %s has exception %s, awaiting', task, e)
            raise e
        return await func(self)
    return wrap

_main_thread_loop = asyncio.get_event_loop()

def set_exc(func):
    @functools.wraps(func)
    async def wrap(self):
        # in case this loads in a diff thread
        try:
            return await func(self)
        except Exception as e:
            self._done.set()
            raise
    return wrap

def wait_or_exit_after(func):
    @functools.wraps(func)
    def wrap(self):
        func(self)
        self._done.wait()
        if self._has_exception:
            logger.error(self._exception)
            _thread.interrupt_main(signal.SIGTERM)
    return wrap
