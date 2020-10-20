import os
import sys
from pathlib import Path

from rvetester.ansys.TestRunner import TestRunner
from rvetester.RVEInputHandler import RVEInputHandler
from rvetester.utils import logger_wraps

SCHEMA_PATH = "./input_schema/input.schema.json"

LAUNCH_OPTIONS = {
    "override": True,
    "run_location": os.getcwd() + "\dump",
    "jobname": "rve_tester",
    "log_apdl": "w",
    "nproc": 4,
}


@logger_wraps()
def main():
    input_file_paths = get_input_file_paths()

    handler = RVEInputHandler(schema_file_path=SCHEMA_PATH)

    RVETestCase = handler.create_testcase_class()

    handler.load_input_files(input_file_paths=input_file_paths)

    cases = [RVETestCase(**input_dict) for input_dict in handler.input_dicts]

    for case in cases:
        case.check_parameters()
        case.attach_to_testrunner(TestRunnerClass=TestRunner, options=LAUNCH_OPTIONS)
        case.run_tests()

    for case in cases:
        print(case.results.reportedProperties)
        case.save_results()


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
