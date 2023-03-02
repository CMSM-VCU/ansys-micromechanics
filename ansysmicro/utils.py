import functools
import time
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from loguru import logger


def logger_wraps(
    _func: Callable = None, *, entry=True, exit=True, level="TRACE"
) -> Callable:
    """Crazy logging decorator, adjusted to enable use in decorate_all_methods function.
    From loguru documentation:
    loguru.readthedocs.io/en/stable/resources/recipes.html#logging-entry-and-exit-of-functions-with-a-decorator

    Args:
        _func (Callable, optional): Function to be wrapped. Defaults to None.
    """

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


def decorate_all_methods(decorator: Callable, *args, **kwargs) -> Callable:
    """Wrap all methods (callable attributes) in a class with the given decorator
    function.

    Args:
        decorator (Callable): Decorator function to apply to methods.
    """

    def decorate(class_):
        for attr in class_.__dict__:
            if callable(getattr(class_, attr)):
                setattr(
                    class_,
                    attr,
                    decorator(getattr(class_, attr), *args, **kwargs),
                )
        return class_

    return decorate


def definitely_delete_file(
    path: Path,
    missing_ok: bool = False,
    max_wait: int = 5,
    return_waited: bool = False,
    warn_on_fail: bool = False,
) -> bool | tuple[bool, int]:
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
            logger.debug("File not deleted yet. Checking again in 1 second...")
            time.sleep(1)
            waited += 1
            continue
        else:
            deleted = not path.exists()
            break
    else:
        msg = f"File not deleted after waiting {waited} seconds."
        if warn_on_fail:
            logger.warning(msg)
        else:
            raise Exception(msg)

    if return_waited:
        return (deleted, waited)
    else:
        return deleted


def definitely_find_file(
    path: Path,
    max_wait: int = 5,
    return_waited: bool = False,
    warn_on_fail: bool = False,
) -> bool | tuple[bool, int]:
    """Try to find a file, and wait until the file exists and has nonzero size.

    Args:
        path (Path): pathlib Path object pointing to target file
        max_wait (int, optional): Maximum number of seconds to wait for successful
            find. Defaults to 5.
        return_waited (bool, optional): Whether to return the number of seconds waited.
            Defaults to False.
        warn_on_fail (bool, optional): Issue warning instead of error when search times
            out. Defaults to False.

    Raises:
        Exception: Failed to find file with nonzero size, with warn_on_fail=False.

    Returns:
        bool: Whether the file exists and has nonzero size.
        int, optional: Number of seconds waited before finding file.
            Only provided if return_waited is True.
    """
    waited = 0
    found = False
    while waited < max_wait:
        if path.exists():
            if path.stat().st_size > 0:
                found = path.stat().st_size > 0
                break
            else:
                logger.debug(
                    f"File found, but size={path.stat().st_size}. Checking again in 1 second..."
                )
                time.sleep(1)
                waited += 1
                continue
        else:
            logger.debug("File not found. Checking again in 1 second...")
            time.sleep(1)
            waited += 1
            continue
    else:
        msg = f"File not found with nonzero size after waiting {waited} seconds."
        if warn_on_fail:
            logger.warning(msg)
        else:
            raise Exception(msg)

    if return_waited:
        return (found, waited)
    else:
        return found


def round_to_sigfigs(array: Sequence, num: int) -> np.ndarray:
    """Round an array-like (something that can be converted to np array) to the
    specified number of significant figures.

    From stackoverflow.com/a/59888924

    Args:
        array (Sequence): Array to be rounded.
        num (int): Number of significant figures.

    Returns:
        np.ndarray: Array after rounding (type changed to array if not already).
    """
    array = np.asarray(array)
    arr_positive = np.where(
        np.isfinite(array) & (array != 0), np.abs(array), 10 ** (num - 1)
    )
    mags = 10 ** (num - 1 - np.floor(np.log10(arr_positive)))
    return np.round(array * mags) / mags


def nonfinite_to_zero(array: np.ndarray) -> np.ndarray:
    """Replace all nonfinite (inf, -inf, NaN) values in an array with 0.0.

    Args:
        array (np.ndarray): Array to be modified.

    Returns:
        np.ndarray: Modified array.
    """
    return np.where(np.isfinite(array), array, 0.0)


def all_same(items: Sequence) -> bool:
    """Check whether all items in a sequence (list, tuple, etc.) are equal to each
    other. Avoiding conversion to np array in case of mixed types.

    Args:
        items (Sequence): Set of items to be checked for equality.

    Returns:
        bool: Whether all items were equal/same.
    """
    return all(x == items[0] for x in items)
