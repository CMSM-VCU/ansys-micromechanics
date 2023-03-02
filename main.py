import os
import shutil
import stat
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

from loguru import logger

from ansysmicro.ansys.TestRunner import TestRunner
from ansysmicro.AnsysInputHandler import AnsysInputHandler
from ansysmicro.utils import logger_wraps

SCHEMA_PATH = "./input_schema/input.schema.json"


@logger_wraps()
def main():
    parser = ArgumentParser()
    parser.add_argument("file", nargs="+", help="The input file to run", type=str)
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="[INACTIVE] Clean up working directory after each case",
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="count", default=0
    )
    args = parser.parse_args()
    if args.verbose > 1:
        logger.remove()
        logger.add(sys.stderr, level="TRACE")
    elif args.verbose > 0:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    logger.debug(f"Command line arguments: {args}")
    cleanup_working_dir = args.cleanup

    input_file_paths = get_input_file_paths(paths=args.file)

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
        logger.info(f"Results: \n{case.results.reportedProperties}")
        case.save_results()
        if cleanup_working_dir:
            logger.debug("cleanup disabled")
            continue
            case.testrunner = None
            logger.debug("waiting before delete...")
            time.sleep(10)
            shutil.rmtree(
                Path(case.runnerOptions.run_location), onerror=remove_readonly
            )


def remove_readonly(func, path, _):
    "Clear the readonly bit and reattempt the removal"
    os.chmod(path, stat.S_IWRITE)
    logger.debug(path)
    func(path)


@logger_wraps()
def get_input_file_paths(paths: list[str | Path]) -> list[Path]:
    """Obtain paths to input files from command line arguments. Assumes that each and
    all arguments are an input file path. Paths must be absolute or relative to calling
    directory. Non-existant files will throw a warning.

    Returns:
        input_paths (list[Path]): List of paths to each input file
    """
    real_paths = []
    for path_ in paths:
        path = Path(path_)
        if "*" in str(path):
            logger.info(f"Reading as glob: {path}")
            glob = list(path.parent.glob(str(path.name)))
            real_paths += glob
        elif path.exists():
            real_paths += [path]
        else:
            logger.warning(f"Input file not found at {path}")

    logger.info(f"Running input files: {real_paths}")

    return real_paths


if __name__ == "__main__":
    main()
