import time
from functools import reduce
from itertools import permutations, product

import numpy as np

from utils import decorate_all_methods, logger_wraps, nonfinite_to_zero

AXES = ["X", "Y", "Z"]
RESULTS_WAIT_MAX = 10


@decorate_all_methods(logger_wraps)
class ResultsHandler:
    def __init__(self, testrunner):
        self.ansys = testrunner.ansys
        self.rst_path = testrunner.rst_path
        self.retained_nodes = testrunner.retained_nodes

        self.results = {}
        self.debug_results = {}

    def clear_results(self):
        self.ansys.finish()

        try:
            self.rst_path.unlink(missing_ok=True)
        except Exception as err:
            raise err

        try:
            assert not self.rst_path.exists()
        except:
            time.sleep(1)
            assert not self.rst_path.exists()
        pass

    def find_results_file(self):
        self.ansys.finish()
        waited = 0
        while waited < RESULTS_WAIT_MAX:
            try:
                assert self.rst_path.exists()
                assert self.rst_path.stat().st_size > 0
                print(f"\nHit: {waited=}")
                break
            except:
                time.sleep(1)
                self.ansys.finish()
                waited += 1
                print("miss... ", end="")
        else:
            raise Exception(f"\nResults file not found: {self.rst_path.exists()=}")

        try:
            result = self.ansys.result
        except:
            self.rst_path.touch()
            result = self.ansys.result

        return result

    def extract_raw_results(self):
        result = self.find_results_file()

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
                nonfinite_to_zero(np.outer(retained_disps[n], 1.0 / rel_coord[n]))
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

