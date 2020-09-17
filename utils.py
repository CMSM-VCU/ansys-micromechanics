import functools
import time
from pathlib import Path
from typing import Tuple, Union
from warnings import warn

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


def definitely_delete_file(
    path: Path,
    missing_ok: bool = False,
    max_wait: int = 5,
    return_waited: bool = False,
    warn_on_fail: bool = False,
) -> Union[bool, Tuple[bool, int]]:
    """Delete the file specified by an absolute or relative path, and wait until the
    file is reported as no longer existing.

    Args:
        path (Path): pathlib Path object pointing to target file
        missing_ok (bool, optional): Whether to allow trying to delete a file that does
            not exist. Defaults to False.
        max_wait (int, optional): Maximum number of seconds to wait for successful
            deletion. Defaults to 5.
        return_waited (bool, optional): Whether to return the number of seconds waited.
            Defaults to False.
        warn_on_fail (bool, optional): Issue warning instead of error when existance
            check times out. Defaults to False.

    Raises:
        err: Error raised by path.unlink(). Deleting a missing file with
            missing_ok=False will trigger this.
        Exception: Existance check has timed out, with warn_on_fail=False.

    Returns:
        bool: Whether the file was confirmed to be deleted.
        int, optional: Number of seconds waited before deletion confirmed.
            Only provided if return_waited is True.
    """
    try:
        path.unlink(missing_ok=missing_ok)
    except Exception as err:
        raise err

    waited = 0
    deleted = False
    while waited < max_wait:
        if path.exists():
            print("File not deleted yet. Checking again in 1 second...")
            time.sleep(1)
            waited += 1
            continue
        else:
            deleted = not path.exists()
            break
    else:
        msg = f"File not deleted after waiting {waited} seconds."
        if warn_on_fail:
            warn(msg)
        else:
            raise Exception(msg)

    if return_waited:
        return (deleted, waited)
    else:
        return deleted


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


def all_same(items):
    return all(x == items[0] for x in items)
