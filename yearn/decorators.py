import _thread
import functools

import sentry_sdk


def sentry_catch_all(func):
    @functools.wraps(func)
    def wrap(self):
        try:
            func(self)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            self._has_exception = True
            self._done.set()
            raise
    return wrap


def wait_or_exit_before(func):
    @functools.wraps(func)
    def wrap(self):
        self._done.wait()
        if self._has_exception:
            _thread.interrupt_main()
        return func(self)
    return wrap


def wait_or_exit_after(func):
    @functools.wraps(func)
    def wrap(self):
        func(self)
        self._done.wait()
        if self._has_exception:
            _thread.interrupt_main()
    return wrap
