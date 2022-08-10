import _thread
import functools
import logging
from typing import Any, Callable, TypeVar, Union

import sentry_sdk

logger = logging.getLogger(__name__)

T = TypeVar("T")


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
            _thread.interrupt_main()
        return func(self)
    return wrap


def wait_or_exit_after(func):
    @functools.wraps(func)
    def wrap(self):
        func(self)
        self._done.wait()
        if self._has_exception:
            logger.error(self._exception)
            _thread.interrupt_main()
    return wrap


def lru_cache_with_exceptions(*lru_cache_args: Any, **lru_cache_kwargs: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    callable_as_sole_arg = len(lru_cache_args) == 1 and callable(lru_cache_args[0])
    if callable_as_sole_arg:
        """
        This means the user decorated a function like so:

        @lru_cache_with_exceptions
        def my_func():
            ...
        
        instead of the argumented version:
        
        @lru_cache_with_exceptions(maxsize=...)
        def my_func():
            ...
        """
        callable_sole_arg = lru_cache_args[0]
        lru_cache_args = tuple()
        lru_cache_kwargs = dict()

    def lru_cache_with_exceptions_decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.lru_cache(*lru_cache_args, **lru_cache_kwargs)
        def try_and_return_result_or_exception(*args, **kwargs) -> Union[T, Exception]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return e

        @functools.wraps(func)
        def lru_cache_with_exceptions_wrap(*args, **kwargs) -> T:
            retval = try_and_return_result_or_exception(*args, **kwargs)
            if isinstance(retval, Exception):
                raise retval
            return retval
        return lru_cache_with_exceptions_wrap
    
    return lru_cache_with_exceptions_decorator(callable_sole_arg) if callable_as_sole_arg else lru_cache_with_exceptions_decorator
