from dataclasses import dataclass, field
from typing import List

import numpy as np

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
    properties: Material = field(init=False, compare=False)

    def run_tests(self):
        """Run set of mechanical tests on cubic RVE. Normal and shear tests each in all
        three directions. Distill results into effective elastic moduli, shear moduli,
        and poisson's ratios.
        """

        with TestRunner() as test_runner:
            print(test_runner)
            test_runner.generate_base_mesh(self.dimensions)
            test_runner.define_materials(self.materials)
            test_runner.apply_periodic_conditions()
            test_runner.generate_load_steps(self.loads)
            test_runner.assign_element_materials(self.arrangement)
            test_runner.solve_load_steps()
            test_runner.extract_raw_results()

            self.properties = test_runner.calculate_properties()
            print("Returned to end of with")
