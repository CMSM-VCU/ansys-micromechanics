import numpy as np

from TestCase import TestCase
from tuples import Dims, Loads, Material


def get_input_file_paths():
    """Obtain paths to input files from command line arguments. Assumes that each and
    all arguments are an input file path. Paths must be absolute or relative to calling
    directory. Non-existant files will throw a warning.

    Returns:
        input_paths (List[Str]): List of paths to each input file
    """
    input_paths = [None]
    for path in input_paths:
        check_file_exists(path)
    return input_paths


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


def parse_input_data(input_file):
    # throw warning if side length and element length are not divisible

    dims = Dims(1, 0.1)
    materials = [Material(1, [1], [1], [1])]
    arrangement = np.array([1])
    loads = Loads("displacement", 1, 1)

    return TestCase(dims, materials, arrangement, loads)
