from dataclasses import dataclass, field
from typing import List
from warnings import warn

import numpy as np

from utils import logger_wraps
from TestRunner import TestRunner
from tuples import Dims, Loads, Material


@dataclass
class TestCase:
    """Contains the parameters and calculates the results for a single test case.

    Attributes:
        dimensions (Dims): geometry of domain and elements
        materials (List[Material]): list of input property sets for each material
        arrangements (Array): array containing centroids of all elements of
        non-default materials
        loads (Loads): type and magnitude of loading for normal and shear tests
        properties (List[Props]): list of effective property sets calculated by tests

    """

    dimensions: Dims
    materials: List[Material]
    arrangement: np.ndarray
    loads: Loads
    properties: Material = field(default=None, init=False, compare=False)

    @logger_wraps()
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
            test_runner.generate_base_mesh(self.dimensions)
            test_runner.define_materials(self.materials)
            test_runner.apply_periodic_conditions(self.dimensions)
            test_runner.generate_load_steps(self.loads, self.dimensions)
            test_runner.assign_element_materials(self.arrangement)
            test_runner.solve_load_steps()
            test_runner.extract_raw_results()

            self.properties = test_runner.calculate_properties()
            print("Returned to end of with")

    @logger_wraps()
    def check_parameters(self):
        passed_checks = True
        elements_per_side = self.dimensions.side_length / self.dimensions.element_length
        if elements_per_side % round(elements_per_side) > 1e-3:
            warn("Domain side length is not evenly divisible by element edge length")
            passed_checks = False

        return passed_checks
