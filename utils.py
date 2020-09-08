import functools

import numpy as np
from loguru import logger

# def logger_wraps(*, entry=True, exit=True, level="DEBUG"):
#     return logger_wrapper(func,)


def logger_wraps(_func=None, *, entry=True, exit=True, level="DEBUG"):
    def logger_wrapper(func):
        name = func.__name__

        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            logger_ = logger.opt(depth=1)
            if entry:
                logger_.log(
                    level, "Entering '{}' (args={}, kwargs={})", name, args, kwargs
                )
            result = func(*args, **kwargs)
            if exit:
                logger_.log(level, "Exiting '{}' (result={})", name, result)
            return result

        return wrapped

    if _func is None:
        return logger_wrapper
    else:
        return logger_wrapper(_func)


def decorate_all_methods(decorator, *args, **kwargs):
    def decorate(class_):
        for attr in class_.__dict__:
            if callable(getattr(class_, attr)):
                setattr(
                    class_, attr, decorator(getattr(class_, attr), *args, **kwargs),
                )
        return class_

    return decorate


@logger_wraps()
def check_file_exists(file_path):
    """Check whether the file of a given path exists. If not, throw a warning and return
    False, otherwise return True.

    Arguments:
        file_path (str) Absolute or relative path to a file

    Returns:
        (bool): Whether the file exists

    Raises:
        Warning: If the file does not exist
    """
    return True


def round_to_sigfigs(array, num):
    # From stackoverflow.com/a/59888924
    array = np.asarray(array)
    arr_positive = np.where(
        np.isfinite(array) & (array != 0), np.abs(array), 10 ** (num - 1)
    )
    mags = 10 ** (num - 1 - np.floor(np.log10(arr_positive)))
    return np.round(array * mags) / mags


def nonfinite_to_zero(array):
    return np.where(np.isfinite(array), array, 0.0)
