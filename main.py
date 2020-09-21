import os
import sys
from pathlib import Path
from pprint import pprint

import utils
from RVEInputHandler import RVEInputHandler
from TestRunner import TestRunner
from utils import logger_wraps

SCHEMA_PATH = "./input_schema/input.schema.json"

LAUNCH_OPTIONS = {
    "override": True,
    "run_location": os.getcwd() + "\dump",
    "jobname": "rve_debug",
    "log_apdl": "w",
    "nproc": 12,
}


@logger_wraps()
def main():
    input_file_paths = get_input_file_paths()

    cases = []

    handler = RVEInputHandler(schema_file_path=SCHEMA_PATH)

    RVETestCase = handler.create_testcase_class()

    handler.load_input_files(input_file_paths=input_file_paths)

    for input_dict in handler.input_dicts:
        cases.append(RVETestCase(**input_dict))

    # fmt: off
    case_result_sets = {
        "E11": [],"E22": [],"E33": [],
        "G12": [],"G13": [],"G23": [],
        "v12": [],"v13": [],"v23": [],"v21": [],"v31": [],"v32": [],
    }
    # fmt: on

    for case in cases:
        case.check_parameters()
        case.attach_to_testrunner(TestRunnerClass=TestRunner, options=LAUNCH_OPTIONS)
        case.run_tests()

    for case in cases:
        print(case.results.reportedProperties)
        case.save_results()

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
        if not Path(path).exists():
            print(f"Input file not found at {path}")
            input_paths.remove(index)
    return input_paths


if __name__ == "__main__":
    main()
