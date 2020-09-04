from warnings import warn

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
        self.testrunner.run()
        print(f"Finished with {self.results}")

    def check_parameters(self):
        passed_checks = True
        try:
            elements_per_side = self.mesh.domainSideLength / self.mesh.elementSpacing
            if elements_per_side % round(elements_per_side) > 1e-3:
                warn(
                    "Domain side length is not evenly divisible by element edge length"
                )
                passed_checks = False
        except AttributeError:
            pass

        return passed_checks

    @property
    def mesh_type(self):
        if getattr(self.mesh, "locationsWithId", None) is not None:
            return "centroid"
        elif getattr(self.mesh, "nodeFileRelativePath", None) is not None:
            return "external"
        else:
            raise Exception("Unable to determine mesh type")

    def decorate_attributes(self):
        if self.mesh_type == "external":
            self.mesh.nodeFileAbsolutePath = str(
                self.path.parent / self.mesh.nodeFileRelativePath
            )

            self.mesh.elementFileAbsolutePath = str(
                self.path.parent / self.mesh.elementFileRelativePath
            )
