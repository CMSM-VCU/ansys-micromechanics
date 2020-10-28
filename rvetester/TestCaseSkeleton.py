from pathlib import Path
from typing import Tuple
from warnings import warn

import numpy as np

from .RecursiveNamespace import RecursiveNamespace
from .utils import decorate_all_methods, logger_wraps, all_same

RUNNER_OPTIONS_DEFAULTS = {
    "override": True,
    "run_location": Path.cwd() / "dump",
    "jobname": "rve_tester",
    "log_apdl": "w",
    "nproc": 4,
}


@decorate_all_methods(logger_wraps)
class TestCaseSkeleton:
    """This class is used as the base for the TestCase class that is created at
    runtime by RecursiveClassFactory in coordination with the input schema. Most of
    the attributes are defined at runtime according the the schema structure and naming.
    """

    def __init__(self):
        self.preprocess_attributes()

    def attach_to_testrunner(self, TestRunnerClass, options=None):
        """Initialize a test runner with a set of options, and tie it and the test case
        together in attributes.

        Args:
            TestRunnerClass (Class): Specific TestRunner class (not instance) to use.
            options ([type], optional): Dictionary of options specific to the TestRunner
            class initialization. Defaults to None.
        """
        self.testrunner = TestRunnerClass(test_case=self, options=options)

    def run_tests(self):
        """Activate testrunner's test sequence, culminating in the delivery of the
        results object.
        """
        self.results = self.testrunner.run()
        print(f"Finished with {self.results.reportedProperties}")
        self.compress_results()

    def compress_results(self) -> bool:
        """Attempt to compress results of multiple load cases into a single set. Only
        works if every property was only calculated in one load case. Adds a new column
        to self.results.reportedProperties containing collected results.

        Returns:
            bool: Whether the results were able to be compressed.

        TODO: Move to ResultsHandler.
        """
        assert self.results, "Results do not exist yet."

        if np.all(self.unique_expected_properties[1] == 1):
            collapsed_column = self.results.reportedProperties.bfill(axis=1).iloc[:, 0]
            collapsed_column.loc["Label"] = "Full"
            self.results.reportedProperties.insert(0, 0, collapsed_column)
            return True
        else:
            print("Results cannot be compressed.")
            return False

    def save_results(self):
        """Save the reportedProperties dataframe to a csv file. Creates a new folder
        `results` in the directory that the input file is in. The file is named
        `[input file name]_[case id].csv`.
        """
        folder = self.path.parent / "results"
        if not folder.is_dir():
            folder.mkdir()
        filename = str(self.path.stem) + "_" + str(self.caseId) + ".csv"
        self.results.reportedProperties.to_csv(str(folder) + "/" + filename)

    def check_parameters(self) -> bool:
        """Run various self-checks on the test case input parameters.

        Returns:
            bool: Whether the parameters passed the checks.

        TODO: Break tests up into separate methods.
        """
        passed_checks = True
        # Check if mapped mesh dimensions are well-behaved
        if self.mesh_type == "centroid":
            elements_per_side = self.mesh.domainSideLength / self.mesh.elementSpacing
            if elements_per_side % round(elements_per_side) > 1e-3:
                warn(
                    "Domain side length is not evenly divisible by element edge length"
                )
                passed_checks = False

        # Check if specified mesh files are able to be found
        if self.mesh_type == "external":
            attrs = [kind + "FileAbsolutePath" for kind in ["node", "element", "csys"]]
            for attr in attrs:
                if (path_ := getattr(self.mesh, attr, None)) is not None:
                    assert Path(path_).exists(), f"{path_} could not be found."

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
                    assert shear_input == shear_theory, (
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
    def mesh_type(self) -> str:
        """What kind of mesh is being used, according to user input parameters.

        Raises:
            Exception: If mesh type is unable to be determined.

        Returns:
            str: Mesh type, currently either "centroid" or "external".
        """
        if getattr(self.mesh, "locationsWithId", None) is not None:
            return "centroid"
        elif getattr(self.mesh, "nodeFileRelativePath", None) is not None:
            return "external"
        else:
            raise Exception("Unable to determine mesh type")

    @property
    def loading_type(self) -> str:
        """What kind of loading is being used, according to user input parameter.

        Returns:
            str: Loading type, currently either "displacement" or "tensor".
        """
        return self.loading.kind

    @property
    def num_load_cases(self) -> int:
        """How many load cases are in this test case, according to length of user input
        parameters.

        Returns:
            int: Number of load cases
        """
        if self.loading.kind == "displacement":
            return len(self.loading.directions)
        elif self.loading.kind == "tensor":
            return len(self.loading.tensors)

    @property
    def unique_expected_properties(self) -> Tuple[np.ndarray]:
        """The array of all unique properties expected by the user, across all load
        cases.

        Returns:
            Tuple[np.ndarray]: Tuple containing array with all unique property strings
            and array with counts of each property.
        """
        return np.unique(np.hstack(self.loading.expectedProperties), return_counts=True)

    def preprocess_attributes(self):
        """Manipulate user input attributes to prepare for future use. Currently,
        setting absolute paths to mesh files from user input relative paths.
        """
        if self.mesh_type == "external":
            self.mesh.nodeFileAbsolutePath = str(
                self.path.parent / self.mesh.nodeFileRelativePath
            )

            self.mesh.elementFileAbsolutePath = str(
                self.path.parent / self.mesh.elementFileRelativePath
            )

        if getattr(self, "runnerOptions", None) is not None:
            dict_from_input = vars(self.runnerOptions)
        else:
            dict_from_input = {}
        self.runnerOptions = RecursiveNamespace(
            **{**RUNNER_OPTIONS_DEFAULTS, **dict_from_input}
        )
        self.runnerOptions.run_location = str(
            Path.resolve(self.path.parent / self.runnerOptions.run_location)
        )
