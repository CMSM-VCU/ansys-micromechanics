from warnings import warn

import numpy as np
import pandas as pd

from utils import decorate_all_methods, logger_wraps, all_same

PLANES_NORMAL = ("11", "22", "33")
PLANES_SHEAR = ("12", "13", "21", "23", "31", "32")


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

    def __init__(self):
        self.decorate_attributes()

    def attach_to_testrunner(self, TestRunnerClass, options=None):
        self.testrunner = TestRunnerClass(test_case=self, options=options)

    def run_tests(self):
        """Run set of mechanical tests on cubic RVE. Normal and shear tests each in all
        three directions. Distill results into effective elastic moduli, shear moduli,
        and poisson's ratios.

        Arguments:
            launch_options (dict, optional): dictionary of keyword arguments for
            TestRunner options
        """
        self.results = self.testrunner.run()
        print(f"Finished with {self.results.reportedProperties}")
        self.compress_results()

    def compress_results(self):
        assert self.results, "Results do not exist yet."

        if np.all(self.unique_expected_properties[1] == 1):
            collapsed_column = self.results.reportedProperties.bfill(axis=1).iloc[:, 0]
            collapsed_column.loc["Label"] = "Full"
            self.results.reportedProperties.insert(0, 0, collapsed_column)
            return True
        else:
            print("Results cannot be compressed.")
            return False

    def check_parameters(self):
        passed_checks = True
        # Check if mapped mesh dimensions are well-behaved
        if self.mesh_type == "centroid":
            elements_per_side = self.mesh.domainSideLength / self.mesh.elementSpacing
            if elements_per_side % round(elements_per_side) > 1e-3:
                warn(
                    "Domain side length is not evenly divisible by element edge length"
                )
                passed_checks = False

        # Check if "fake" isotropic materials obey Hooke's Law
        for mat in self.materials:
            if mat.materialType == "orthotropic":
                prop_sets = [
                    mat.elasticModuli,
                    mat.shearModuli,
                    mat.poissonsRatios,
                ]
                if all([all_same(prop) for prop in prop_sets]):
                    shear_input = mat.shearModuli[0]
                    shear_theory = mat.elasticModuli[0] / (
                        2 * (1 + mat.poissonsRatios[0])
                    )
                    try:
                        assert shear_input == shear_theory
                    except:
                        raise ValueError(
                            f"Material {mat.materialIndex} is isotropic but does not "
                            + "obey Hooke's Law: {shear_input=}, {shear_theory=}"
                        )

        # Check if a label has been provided for each load case, if any
        if getattr(self.loading, "labels", None) is not None:
            assert len(self.loading.labels) == self.num_load_cases, (
                f"Number of labels must equal number of load cases. "
                + f"{len(self.loading.labels)} labels given for {self.num_load_cases} load cases."
            )
        else:
            self.loading.labels = None  # Prevent future AttributeErrors

        # Check for impossible expected properties
        # fmt: off
        forbidden_props = (
            "E12", "E13", "E21", "E23", "E31", "E32",
            "G11", "G22", "G33",
            "v11", "v22", "v33"
        )
        # fmt: on
        assert not (
            bad_props := [
                prop
                for prop in self.unique_expected_properties[0]
                if prop in forbidden_props
            ]
        ), f"Expected properties contains impossible property(s): {bad_props}"

        # Check for duplicate expected properties in same load case
        for i, prop_set in enumerate(self.loading.expectedProperties):
            assert len(prop_set) == len(set(prop_set)), (
                f"Expected properties contains duplicates "
                + f"in single load case: {i+1}: {prop_set}"
            )

        return passed_checks

    @property
    def mesh_type(self):
        if getattr(self.mesh, "locationsWithId", None) is not None:
            return "centroid"
        elif getattr(self.mesh, "nodeFileRelativePath", None) is not None:
            return "external"
        else:
            raise Exception("Unable to determine mesh type")

    @property
    def loading_type(self):
        return self.loading.kind

    @property
    def num_load_cases(self):
        if self.loading.kind == "displacement":
            return len(self.loading.directions)
        elif self.loading.kind == "tensor":
            return len(self.loading.tensors)

    @property
    def unique_expected_properties(self):
        return np.unique(np.hstack(self.loading.expectedProperties), return_counts=True)

    def decorate_attributes(self):
        if self.mesh_type == "external":
            self.mesh.nodeFileAbsolutePath = str(
                self.path.parent / self.mesh.nodeFileRelativePath
            )

            self.mesh.elementFileAbsolutePath = str(
                self.path.parent / self.mesh.elementFileRelativePath
            )
