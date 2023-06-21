import _thread
import signal
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
    def wrap(self):
        self._done.wait()
        if self._has_exception:
            logger.error(self._exception)
            _thread.interrupt_main(signum=signal.SIGTERM)
        return func(self)
    return wrap


def wait_or_exit_after(func):
    @functools.wraps(func)
    def wrap(self):
        func(self)
        self._done.wait()
        if self._has_exception:
            logger.error(self._exception)
            _thread.interrupt_main(signum=signal.SIGTERM)
    return wrap
