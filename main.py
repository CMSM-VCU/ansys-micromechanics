import os
import sys

import utils
from RVEInputHandler import RVEInputHandler
from utils import logger_wraps

SCHEMA_PATH = "./input_schema/input.schema.json"

LAUNCH_OPTIONS = {
    "override": True,
    "run_location": os.getcwd() + "\dump",
    "jobname": "rve_debug",
    "log_apdl": "w",
}


@logger_wraps()
def main():
    input_file_paths = get_input_file_paths()

    cases = []

    handler = RVEInputHandler(schema_file_path=SCHEMA_PATH)

    handler.load_input_files(input_file_paths=input_file_paths)

    for input_dict in handler.input_dicts:
        cases.append(handler.convert_input_dict_to_testcase(input_dict=input_dict))

    for case in cases:
        case.check_parameters()
        case.run_tests(launch_options=LAUNCH_OPTIONS)

        print(case.properties)

    pass


@logger_wraps()
def get_input_file_paths():
    """Obtain paths to input files from command line arguments. Assumes that each and
    all arguments are an input file path. Paths must be absolute or relative to calling
    directory. Non-existant files will throw a warning.

    Returns:
        input_paths (List[Str]): List of paths to each input file
    """
    input_paths = sys.argv[1:]
    for index, path in reversed(list(enumerate(input_paths))):
        if not utils.check_file_exists(path):
            input_paths.remove(index)
    return input_paths


if __name__ == "__main__":
    main()
