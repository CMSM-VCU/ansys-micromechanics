import time
from functools import reduce
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd
from pyansys.rst import ResultFile

import utils
from RecursiveNamespace import RecursiveNamespace

AXES = ["X", "Y", "Z"]
RESULTS_WAIT_MAX = 10


@utils.decorate_all_methods(utils.logger_wraps)
class ResultsHandler:
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
            rst_path = self.rst_path

        self.ansys.finish()  # Safely close results file before deletion

        return utils.definitely_delete_file(rst_path, missing_ok=True)

    def get_results_object(
        self, rst_path: Path = None, max_wait=RESULTS_WAIT_MAX
    ) -> ResultFile:
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

    def extract_raw_results(self):
        result = self.get_results_object()

        coord = result.mesh.nodes
        nnum, disp = result.nodal_displacement(result.nsets - 1)

        self.ansys.run("/POST1")
        self.retained_results = []
        for n in self.retained_nodes:
            n_results = {}
            n_idx = np.argwhere(nnum == n)[0, 0]
            n_results["coord"] = coord[n_idx]
            n_results["disp"] = disp[n_idx]

            force_n = []
            for i in range(3):
                appended = False
                while not appended:
                    force_n.append(
                        self.ansys.get(
                            par="rforce",
                            entity="NODE",
                            entnum=n,
                            item1="RF",
                            it1num=f"F{AXES[i]}",
                        )
                    )

                    if type(force_n[-1]) == float and force_n[-1] != "":
                        appended = True
                        continue
                    else:
                        try:
                            time.sleep(1)
                            force_n[-1] = self.ansys.parameters["rforce"]
                            if type(force_n[-1]) == float and force_n[-1] != "":
                                appended = True
                                continue
                        except:
                            print(f"Retrieval failed. Trying again: {n}, {i}")
                            force_n.pop()

                # force_n.append(self.ansys.parameters[f"RFORCE{i+1}"])
            assert len(force_n) == 3
            n_results["force"] = np.array(force_n)

            self.retained_results.append(n_results)

        pass

    def calculate_macro_tensors(self, load_case):
        retained_coords = [
            node_result["coord"] for node_result in self.retained_results
        ]
        retained_disps = [node_result["disp"] for node_result in self.retained_results]
        retained_forces = [
            node_result["force"] for node_result in self.retained_results
        ]
        macro_stress = self.calculate_macro_stress(retained_coords, retained_forces)

        macro_strain_true = self.calculate_macro_strain_true(
            retained_coords, retained_disps
        )
        macro_strain = self.calculate_macro_strain(retained_coords, retained_disps)

        debug_results = {}
        debug_results["retained_results"] = self.retained_results
        debug_results["macro_stress"] = macro_stress
        debug_results["macro_strain_true"] = macro_strain_true
        debug_results["macro_strain"] = macro_strain
        self.debug_results[load_case] = debug_results

        return macro_stress, macro_strain, macro_strain_true

    def calculate_macro_stress(self, retained_coords, retained_forces):
        vol = self.ansys.mesh.grid.volume
        rel_coord = [retained_coords[i] - retained_coords[0] for i in range(4)]
        return (
            reduce(
                lambda x, y: x + y,
                [np.outer(rel_coord[i], retained_forces[i]) for i in range(4)],
            )
            / vol
        )

    def calculate_macro_strain_true(self, retained_coords, retained_disps):
        rel_coord = [retained_coords[i] - retained_coords[0] for i in range(4)]
        return reduce(  # I know it's not "true" strain. Can't remember what this should be called
            lambda x, y: x + y,
            [
                utils.nonfinite_to_zero(np.outer(retained_disps[n], 1.0 / rel_coord[n]))
                for n in range(1, 4)
            ],
        )

    def calculate_macro_strain(self, retained_coords, retained_disps):
        m_s_true = self.calculate_macro_strain_true(retained_coords, retained_disps)
        return 0.5 * (m_s_true + np.transpose(m_s_true))

    def calculate_properties(self, load_case):
        macro_stress, macro_strain, macro_strain_true = self.calculate_macro_tensors(
            load_case
        )

        properties = {}
        properties["elasticModuli"] = [
            macro_stress[i, i] / macro_strain[i, i] for i in range(3)
        ]
        properties["poissonsRatios"] = [
            -1.0 * macro_strain[j, j] / macro_strain[i, i]
            for i, j in permutations(range(3), r=2)
        ]
        properties["shearModuli"] = [
            macro_stress[j, i] / macro_strain_true[j, i]
            for i, j in permutations(range(3), r=2)
        ]

        self.results[load_case] = properties

    def compile_results(self, expected_property_sets, num_load_cases, labels=None):
        assert num_load_cases == len(self.results), (
            f"Expected {num_load_cases} results sets "
            + f"but have {len(self.results)}."
        )

        if len(expected_property_sets) == 1 and num_load_cases > 1:
            expected_property_sets = expected_property_sets * num_load_cases

        key_map = {"E": "elasticModuli", "G": "shearModuli", "v": "poissonsRatios"}
        index_map = dict(
            zip(["".join(pair) for pair in permutations("123", r=2)], range(6))
        )
        index_map.update(dict(zip(["11", "22", "33"], range(3))))

        df_index = list(np.unique(np.hstack(expected_property_sets)))
        if labels:
            df_index = ["Label"] + df_index
        reportedProperties = pd.DataFrame(index=df_index, columns=self.results.keys())
        if labels:
            reportedProperties.loc["Label"] = labels

        for prop_set, (load_case, results_set) in zip(
            expected_property_sets, self.results.items()
        ):
            for prop in prop_set:
                key = prop[0]
                idx = prop[1:]
                reportedProperties.loc[prop, load_case] = results_set[key_map[key]][
                    index_map[idx]
                ]

        results = RecursiveNamespace(
            **{"reportedProperties": None, "full_results": None, "debug_results": None}
        )
        results.reportedProperties = reportedProperties
        results.full_results = self.results
        results.debug_results = self.debug_results

        return results
