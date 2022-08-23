import time
from functools import reduce
from itertools import permutations
from pathlib import Path
from typing import Sequence, Tuple

import numpy as np
import pandas as pd
from ansys.mapdl.reader.rst import Result

import ansysmicro.utils as utils
from ansysmicro.RecursiveNamespace import RecursiveNamespace

AXES = ["X", "Y", "Z"]
RESULTS_WAIT_MAX = 10
# fmt: off
AVAILABLE_PROPERTIES=(
    "E11", "E22", "E33",
    "G12", "G13", "G21","G23", "G31", "G32",
    "v12", "v13", "v21","v23", "v31", "v32"
)
# fmt: on


@utils.decorate_all_methods(utils.logger_wraps)
class ResultsHandler:
    """Handler for extracting and processing results from Ansys RVE test sequence. The
    ResultsHandler instance is paired with a TestRunner instance on initialization.
    """

    def __init__(self, testrunner):
        self.ansys = testrunner.ansys
        self.rst_path = testrunner.rst_path
        self.retained_nodes = testrunner.retained_nodes

        self.results = {}
        self.debug_results = {}

    def clear_results(self, rst_path: Path = None) -> bool:
        """Delete current results file to ensure correct recording of next load case.

        Args:
            rst_path (Path, optional): absolute or relative path to results file.
                Defaults to None, which falls back to the rst_path class attribute.

        Returns:
            bool: Whether the results file was successfully deleted.
        """
        if rst_path is None:
            if self.rst_path is None:
                return True
            rst_path = self.rst_path

        self.ansys.finish()
        return utils.definitely_delete_file(rst_path, missing_ok=True)

    def get_results_object(
        self, rst_path: Path = None, max_wait=RESULTS_WAIT_MAX
    ) -> Result:
        """Extract results object from results file (.rst) of current Ansys instance.

        Args:
            rst_path (Path, optional): pathlib Path object pointing to results file.
                Defaults to None, which falls back to the rst_path class attribute.
            max_wait (int, optional): Maximum number of seconds to wait to find results
                file. Defaults to RESULTS_WAIT_MAX.

        Returns:
            pyansys.rst.ResultFile: Extracted pyansys results file object.
        """
        if rst_path is None:
            rst_path = self.rst_path

        self.ansys.finish()

        assert utils.definitely_find_file(
            rst_path, max_wait=max_wait
        ), "Could not find results file."

        return self.ansys.result

    def extract_raw_results(self, retained_nodes: Sequence = None) -> Tuple[dict]:
        """Extract coordinates, displacemenets, and reaction forces from retained nodes.
        Each node's data is stored in a dict, with dicts stored in a tuple.

        Args:
            retained_nodes (Sequence, optional): List of retained node numbers. Defaults
                to None, which falls back to the retained_nodes class attribute.

        Returns:
            Tuple[dict]: Tuple containing results data, stored in a dictionary for each
                node. Dict keys are "coord", "disp", and "force", each containing a
                (3,) np.ndarray
        """
        if retained_nodes is None:
            retained_nodes = self.retained_nodes
        result = self.get_results_object()

        coord = result.mesh.nodes
        nnum, disp = result.nodal_displacement(result.nsets - 1)

        self.ansys.post1()
        retained_results = []
        for node_num in retained_nodes:
            node_index = np.argwhere(nnum == node_num)[0, 0]
            node_results = {
                "coord": coord[node_index],
                "disp": disp[node_index],
                "force": self.extract_reaction_forces(node_number=node_num),
            }

            retained_results.append(node_results)
        self.retained_results = tuple(retained_results)
        return self.retained_results

    def extract_reaction_forces(self, node_number: int) -> np.ndarray:
        """Extract calculated reaction forces at a node from Ansys. There appears to be
        some race condition in the pyansys get() command, so extra measures must be
        taken to ensure the data is correctly extracted.

        Args:
            node_number (int): Number of the node whose reaction forces to extract

        Returns:
            np.ndarray: Vector of reaction force components, shape=(3,)
        """
        force_n = [0.0, 0.0, 0.0]
        vals, nnums, comps = self.ansys.result.nodal_reaction_forces(0)
        idx = nnums == node_number
        for val, comp in zip(vals[idx], comps[idx]):
            force_n[comp - 1] = val
        return np.array(force_n)

    def calculate_macro_tensors(
        self, load_case: int, retained_results: Tuple[dict] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate the macroscopic tensors for the current load case using the
        retained node results.

        Args:
            load_case (int): Load case number, for indexing debug data
            retained_results (Tuple[dict], optional): Dicts containing retained node
                results data. Defaults to None, which falls back to the retained_results
                class attribute.

        Returns:
            macro_stress (np.ndarray): Macroscopic stress tensor, shape=(3,3)
            macro_strain (np.ndarray): Macroscopic strain tensor, shape=(3,3)
            displacement_gradient (np.ndarray): Macroscopic displacement gradient
                tensor, shape=(3,3)

        TODO: Convert to static method - Require retained_results argument, add option
        to return debug_results, remove load_case argument
        """
        if retained_results is None:
            retained_results = self.retained_results

        retained_coords = [node_result["coord"] for node_result in retained_results]
        retained_disps = [node_result["disp"] for node_result in retained_results]
        retained_forces = [node_result["force"] for node_result in retained_results]

        macro_stress = ResultsHandler.calculate_macro_stress(
            retained_coords, retained_forces, self.ansys.mesh.grid.volume
        )

        displacement_gradient = ResultsHandler.calculate_displacement_gradient(
            retained_coords, retained_disps
        )
        macro_strain = ResultsHandler.calculate_macro_strain(
            retained_coords, retained_disps
        )

        debug_results = {
            "retained_results": retained_results,
            "macro_stress": macro_stress,
            "displacement_gradient": displacement_gradient,
            "macro_strain": macro_strain,
        }
        self.debug_results[load_case] = debug_results

        return macro_stress, macro_strain, displacement_gradient

    @staticmethod
    def calculate_macro_stress(
        retained_coords: Sequence[np.ndarray],
        retained_forces: Sequence[np.ndarray],
        volume: float,
    ) -> np.ndarray:
        """Calculate the macroscopic stress tensor using retained node results.

        Args:
            retained_coords (Sequence[np.ndarray]): Coordinate vectors of retained
                nodes.
            retained_forces (Sequence[np.ndarray]): Reaction force vectors of retained
                nodes.
            volume (float): Volume of RVE

        Returns:
            np.ndarray: Macroscopic stress tensor, shape=(3,3)
        """
        rel_coord = [retained_coords[i] - retained_coords[0] for i in range(4)]
        return (
            reduce(
                lambda x, y: x + y,
                [np.outer(rel_coord[i], retained_forces[i]) for i in range(4)],
            )
            / volume
        )

    @staticmethod
    def calculate_displacement_gradient(
        retained_coords: Sequence[np.ndarray],
        retained_disps: Sequence[np.ndarray],
    ) -> np.ndarray:
        """Calculate the macroscopic displacement gradient tensor using retained node
        results.

        Args:
            retained_coords (Sequence[np.ndarray]): Coordinate vectors of retained
                nodes.
            retained_disps (Sequence[np.ndarray]): Displacement vectors of retained
                nodes.

        Returns:
            np.ndarray: Macroscopic displacement gradient tensor, shape=(3,3)
        """
        rel_coord = [retained_coords[i] - retained_coords[0] for i in range(4)]
        return reduce(  # I know it's not "true" strain. Can't remember what this should be called
            lambda x, y: x + y,
            [
                utils.nonfinite_to_zero(np.outer(retained_disps[n], 1.0 / rel_coord[n]))
                for n in range(1, 4)
            ],
        )

    @staticmethod
    def calculate_macro_strain(
        retained_coords: Sequence[np.ndarray],
        retained_disps: Sequence[np.ndarray],
    ) -> np.ndarray:
        """Calculate the macroscopic strain tensor using retained node results. Uses
        macroscopic displacement gradient.

        Args:
            retained_coords (Sequence[np.ndarray]): Coordinate vectors of retained
                nodes.
            retained_disps (Sequence[np.ndarray]): Displacement vectors of retained
                nodes.

        Returns:
            np.ndarray: Macroscopic strain tensor, shape=(3,3)
        """
        disp_grad = ResultsHandler.calculate_displacement_gradient(
            retained_coords, retained_disps
        )
        return 0.5 * (disp_grad + np.transpose(disp_grad))

    def calculate_properties(self, load_case: int) -> dict:
        """Calculate effective property sets for this load case, using retained node
        results. Effective properties are stored in a dict of 1D arrays like so:
        "elasticModuli":  [E11, E22, E33]
        "shearModuli":    [G12, G13, G21, G23, G31, G32]
        "poissonsRatios": [v12, v13, v21, v23, v31, v32]

        Note: It is unlikely for all effective properties to be computable in one load
        case. This method will give unrealistic values for these properties, and it is
        up to the user to recognize and ignore them.

        Args:
            load_case (int): Load case number, for indexing results data.

        Returns:
            dict: Dictionary containing the three arrays of effective properties.

        TODO: Add retained_results to arguments
        """
        (
            macro_stress,
            macro_strain,
            displacement_gradient,
        ) = self.calculate_macro_tensors(load_case, self.retained_results)

        properties = {
            "elasticModuli": [
                macro_stress[i, i] / macro_strain[i, i] for i in range(3)
            ],
            "poissonsRatios": [
                -1.0 * macro_strain[j, j] / macro_strain[i, i]
                for i, j in permutations(range(3), r=2)
            ],
        }

        properties["shearModuli"] = [
            macro_stress[j, i] / displacement_gradient[j, i]
            for i, j in permutations(range(3), r=2)
        ]

        self.results[load_case] = properties
        return self.results[load_case]

    @staticmethod
    def compile_results(
        results: dict,
        expected_property_sets: Sequence[Sequence],
        num_load_cases: int,
        labels: Sequence[str] = None,
        debug_results: dict = None,
    ) -> RecursiveNamespace:
        """Package calculated properties and other results into single object.

        Args:
            results (dict): Dictionary containing dictionary of calculated properties
                for each load case
            expected_property_sets (Sequence[Sequence]): List of property strings
                requested from load cases.
            num_load_cases (int): Total number of load cases
            labels (Sequence[str], optional): List of labels for each load case.
                Defaults to None.
            debug_results (dict, optional): Dictionary containing miscellaneous results
                sets, useful for debugging. Defaults to None.

        Returns:
            RecursiveNamespace: Object containing the reported properties, results sets,
                and debug results sets as attributes.
        """

        reportedProperties = ResultsHandler.collect_expected_properties(
            results, expected_property_sets, num_load_cases, labels
        )

        compiled_results = RecursiveNamespace(
            **{"reportedProperties": None, "full_results": None, "debug_results": None}
        )
        compiled_results.reportedProperties = reportedProperties
        compiled_results.full_results = results
        if debug_results is not None:
            compiled_results.debug_results = debug_results

        return compiled_results

    @staticmethod
    def collect_expected_properties(
        results: dict,
        expected_property_sets: Sequence[Sequence],
        num_load_cases: int,
        labels: Sequence[str] = None,
    ) -> pd.DataFrame:
        """Collect requested material properties from results of each load case.

        Args:
            results (dict): Dictionary containing dictionary of calculated properties
                for each load case
            expected_property_sets (Sequence[Sequence]): List of property strings
                requested from load cases.
            num_load_cases (int): Total number of load cases
            labels (Sequence[str], optional): List of labels for each load case.
                Defaults to None.

        Returns:
            pd.DataFrame: Dataframe containing requested material properties. Columns
                are load cases and rows are properties. A property not requested for a
                load case is stored as NaN.
        """
        assert num_load_cases == len(
            results
        ), f"Expected {num_load_cases} results sets but have {len(results)}."

        # If a property set is (starts with) "all", replace with all available options
        for i, prop_set in enumerate(expected_property_sets):
            if isinstance(prop_set[0], str) and prop_set[0].lower() == "all":
                expected_property_sets[i] = list(AVAILABLE_PROPERTIES)

        # Extend property set to all load cases if only one given
        if len(expected_property_sets) == 1 and num_load_cases > 1:
            expected_property_sets = expected_property_sets * num_load_cases

        # Maps between property strings and results dict keys and indeces
        key_map = {"E": "elasticModuli", "G": "shearModuli", "v": "poissonsRatios"}
        index_map = dict(
            zip(["".join(pair) for pair in permutations("123", r=2)], range(6))
        ) | dict(zip(["11", "22", "33"], range(3)))

        # Create dataframe and add labels if given
        df_index = list(np.unique(np.hstack(expected_property_sets)))
        if labels:
            df_index = ["Label"] + df_index
        reportedProperties = pd.DataFrame(index=df_index, columns=results.keys())
        if labels:
            reportedProperties.loc["Label"] = labels

        # Get properties from load case results sets
        for prop_set, (load_case, results_set) in zip(
            expected_property_sets, results.items()
        ):
            for prop in prop_set:
                key = prop[0]
                idx = prop[1:]
                reportedProperties.loc[prop, load_case] = results_set[key_map[key]][
                    index_map[idx]
                ]

        return reportedProperties
