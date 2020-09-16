import json
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
        self.testrunner.run()
        print(f"Finished with {self.results}")
        self.debug_write_results()

    def check_parameters(self):
        passed_checks = True
        try:
            elements_per_side = self.mesh.domainSideLength / self.mesh.elementSpacing
            if elements_per_side % round(elements_per_side) > 1e-3:
                warn(
                    "Domain side length is not evenly divisible by element edge length"
                )
                passed_checks = False
        except AttributeError as err:
            print(err)

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

        return passed_checks

    def debug_write_results(self):
        # results = {key: vars(self)[key] for key in ["results"]}
        # for _, result_set in results.items():
        #     for _, load_case in result_set.items():
        #         for _, dataset in load_case.items():
        #             if isinstance(dataset, np.ndarray):
        #                 dataset = dataset.tolist()

        # with open("debug/testOutput2.json", mode="w") as f:
        #     json.dump(results, f)
        # pass

        # Yes, this is really ugly
        e_df = pd.DataFrame.from_dict(
            {i: self.results[i]["elasticModuli"] for i in self.results.keys()}
        )
        e_df = e_df.replace([np.inf, -np.inf, np.nan], 0.0)
        e_df[abs(e_df.max().max() / e_df) > 1e6] = 0.0
        e_df.insert(0, "plane", pd.Series(PLANES_NORMAL, index=e_df.index))
        e_df.insert(0, "var", pd.Series(["E"] * len(e_df[1]), index=e_df.index))

        nu_df = pd.DataFrame.from_dict(
            {i: self.results[i]["poissonsRatios"] for i in self.results.keys()}
        )
        nu_df = nu_df.replace([np.inf, -np.inf, np.nan], 0.0)
        nu_df = nu_df.apply(
            lambda x: [y if (y <= 1.0 and y >= 0.0) else 0.0 for y in x]
        )
        nu_df.insert(0, "plane", pd.Series(PLANES_SHEAR, index=nu_df.index))
        nu_df.insert(0, "var", pd.Series(["nu"] * len(nu_df[1]), index=nu_df.index))

        g_df = pd.DataFrame.from_dict(
            {i: self.results[i]["shearModuli"] for i in self.results.keys()}
        )
        g_df = g_df.replace([np.inf, -np.inf, np.nan], 0.0)
        g_df.insert(0, "plane", pd.Series(PLANES_SHEAR, index=g_df.index))
        g_df.insert(0, "var", pd.Series(["G"] * len(g_df[1]), index=g_df.index))

        results_df = pd.concat([e_df, nu_df, g_df], ignore_index=True)

        print(results_df)
        pass

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

    def decorate_attributes(self):
        if self.mesh_type == "external":
            self.mesh.nodeFileAbsolutePath = str(
                self.path.parent / self.mesh.nodeFileRelativePath
            )

            self.mesh.elementFileAbsolutePath = str(
                self.path.parent / self.mesh.elementFileRelativePath
            )
