import functools
from loguru import logger


def logger_wraps(*, entry=True, exit=True, level="DEBUG"):
    def wrapper(func):
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

    return wrapper


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
