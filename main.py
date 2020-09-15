import csv
import os
from pprint import pprint
import sys

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
        case_result_sets = extract_okereke_data(case, case_result_sets)

    pprint(case_result_sets)
    with open("debug/testOutput.csv", mode="w", newline="") as f:
        csv_output = csv.writer(f)
        for key, item in case_result_sets.items():
            csv_output.writerow([key] + item)
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


def extract_okereke_data(case, set_):
    results = case.results

    set_["E11"].append(results[1]["elasticModuli"][0])
    set_["E22"].append(results[2]["elasticModuli"][1])
    set_["E33"].append(results[3]["elasticModuli"][2])
    set_["G12"].append(results[4]["shearModuli"][0])
    set_["G13"].append(results[6]["shearModuli"][4])  # according to the order output
    set_["G23"].append(results[5]["shearModuli"][3])  # by itertools.permutations()
    set_["v12"].append(results[1]["poissonsRatios"][0])
    set_["v13"].append(results[1]["poissonsRatios"][1])
    set_["v23"].append(results[2]["poissonsRatios"][3])  # according to the order output
    set_["v21"].append(results[2]["poissonsRatios"][2])  # by itertools.permutations()
    set_["v31"].append(results[3]["poissonsRatios"][4])
    set_["v32"].append(results[3]["poissonsRatios"][5])

    return set_


if __name__ == "__main__":
    main()
