from datetime import datetime
import functools
import os
import errno
import signal
import time

FUNCTION_TIME_DICT = {}


class TimeoutError(Exception):
    pass


def time_statistic(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        cost = end_time - start_time
        if func.__name__ not in FUNCTION_TIME_DICT:
            FUNCTION_TIME_DICT[func.__name__] = (cost, 1)
        else:
            FUNCTION_TIME_DICT[func.__name__] = (
                FUNCTION_TIME_DICT[func.__name__][0] + cost,
                FUNCTION_TIME_DICT[func.__name__][1] + 1,
            )
        # print("Time cost of", func.__name__, "is", end_time - start_time)
        return result

    return wrapper


def logme(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("Calling function", func.__name__)
        return func(*args, **kwargs)

    return wrapper


def print_time_statistic():
    for func_name, (cost, count) in FUNCTION_TIME_DICT.items():
        print(f"Function: {func_name}, time cost: {cost}, call count: {count}")

# can only be used in linux
def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator
