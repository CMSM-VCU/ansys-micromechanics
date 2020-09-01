from dataclasses import dataclass
from warnings import warn

from TestRunner import TestRunner
from utils import decorate_all_methods, logger_wraps


@decorate_all_methods(logger_wraps)
class TestCaseSkeleton:
    """Contains the parameters and calculates the results for a single test case.

    Attributes:
        dimensions (Dims): geometry of domain and elements
        materials (List[Material]): list of input property sets for each material
        arrangements (Array): array containing centroids of all elements of
        non-default materials
        loads (Loads): type and magnitude of loading for normal and shear tests
        properties (List[Props]): list of effective property sets calculated by tests

    """

    results: dict

    def attach_to_testrunner(self, TestRunnerClass, options=None):
        self.testrunner = TestRunnerClass(testcase=self)

    def run_tests(self, launch_options=None):
        """Run set of mechanical tests on cubic RVE. Normal and shear tests each in all
        three directions. Distill results into effective elastic moduli, shear moduli,
        and poisson's ratios.

        Arguments:
            launch_options (dict, optional): dictionary of keyword arguments for
            TestRunner options
        """

        with TestRunner(launch_options=launch_options) as test_runner:
            print(test_runner)
            test_runner.prepare_mesh(self.dimensions, self.materials, self.arrangement)
            test_runner.run_test_sequence(self.loads)

            self.properties = test_runner.calculate_properties()
            print("Returned to end of with")

    def check_parameters(self):
        passed_checks = True
        elements_per_side = self.dimensions.side_length / self.dimensions.element_length
        if elements_per_side % round(elements_per_side) > 1e-3:
            warn("Domain side length is not evenly divisible by element edge length")
            passed_checks = False

        return passed_checks
