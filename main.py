import os
import sys
from pathlib import Path

from ansysmicro.ansys.TestRunner import TestRunner
from ansysmicro.AnsysInputHandler import AnsysInputHandler
from ansysmicro.utils import logger_wraps

SCHEMA_PATH = "./input_schema/input.schema.json"


@logger_wraps()
def main():
    input_file_paths = get_input_file_paths()

    handler = AnsysInputHandler(schema_file_path=SCHEMA_PATH)

    TestCaseClass = handler.create_testcase_class()

    handler.load_input_files(input_file_paths=input_file_paths)

    cases = [TestCaseClass(**input_dict) for input_dict in handler.input_dicts]

    for case in cases:
        case.check_parameters()
        case.attach_to_testrunner(
            TestRunnerClass=TestRunner, options=vars(case.runnerOptions)
        )
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
    real_paths = []
    for path_ in input_paths:
        path = Path(path_)
        if "*" in str(path):
            print(f"Reading as glob: {path}")
            glob = list(path.parent.glob(str(path.name)))
            real_paths += glob
        elif path.exists():
            real_paths += path
        else:
            print(f"Input file not found at {path}")

    print(f"Running input files: {real_paths}")

    return real_paths


if __name__ == "__main__":
    main()
