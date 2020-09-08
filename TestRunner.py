from itertools import permutations, product
from functools import reduce
from typing import Any, List

import numpy as np
import pyansys

from AnsysContainer import AnsysContainer
from PBCHandler import PBCHandler
from utils import decorate_all_methods, logger_wraps

AXES = ["X", "Y", "Z"]

# Axes that will always be constrained for each retained node
NORMAL_FIXED_AXES = [["UX", "UY", "UZ"], ["UY", "UZ"], ["UX", "UZ"], ["UX", "UY"]]
SHEAR_FIXED_AXES = [
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
]


@decorate_all_methods(logger_wraps)
class TestRunner:
    ansys: Any  #: pyansys.mapdl_corba.MapdlCorba # don't know how to type hint this
    launch_options: dict
    retained_nodes: List[int]
    retained_results: List[dict]

    def __init__(self, test_case, options=None):
        """Launches an Ansys instance. See pyansys documentation for launch options such
        as job directory and executable path.

        Args:
            launch_options (dict, optional): dictionary of keyword arguments for pyansys.launch_mapdl()
        """
        self.test_case = test_case
        self.test_case.results = []
        self.launch_options = options
        try:
            self.jobname = options["jobname"]
        except:
            print("No jobname found. Defaulting to `file`")
            self.jobname = "file"
        try:
            self.jobdir = options["run_location"] + "\\"
        except:
            print("No jobdir found. Defaulting to `.\`")
            self.jobdir = ".\\"

    def run(self):
        with AnsysContainer(self.launch_options) as self.ansys:
            self.ansys.finish()
            self.ansys.run("/CLEAR")
            self.prepare_mesh()
            self.run_test_sequence()

    def prepare_mesh(self):
        if self.test_case.mesh_type == "centroid":
            self.generate_base_mesh()
            self.assign_element_materials()
        elif self.test_case.mesh_type == "external":
            self.load_external_mesh()
        self.debug_stat()
        self.define_materials()
        self.get_retained_nodes()
        self.pbc_handler = PBCHandler(self)
        self.pbc_handler.apply_periodic_conditions()

    def run_test_sequence(self):
        for load_case in range(1, 7):

            self.ansys.run("/SOLU")
            self.ansys.allsel()
            self.ansys.ddele("ALL")  # Will need to change for any other loading methods
            if load_case < 4:
                self.apply_loading_normal(load_case)
            elif load_case >= 4:
                self.apply_loading_shear(load_case - 3)

            self.solve()
            self.debug_stat()
            self.extract_raw_results()
            self.calculate_properties()

    def load_external_mesh(self):
        self.ansys.run("/prep7")
        self.ansys.et(1, self.test_case.mesh.elementType)
        self.ansys.nread(self.test_case.mesh.nodeFileAbsolutePath)
        self.ansys.eread(self.test_case.mesh.elementFileAbsolutePath)

        assert self.ansys.mesh.n_node > 0
        assert self.ansys.mesh.n_elem > 0

    def generate_base_mesh(self):
        """Generate uniform cubic mesh according to overall side length and element edge
        length. Assumes a cube centered around (0,0,0).

        Args:
            dimensions (Dims): tuple containing side length and element length
        """
        print("generate_base_mesh")
        half_side = self.test_case.mesh.domainSideLength / 2
        self.ansys.run("/PREP7")
        self.ansys.block(
            -half_side, half_side, -half_side, half_side, -half_side, half_side,
        )

        self.ansys.et(1, self.test_case.mesh.elementType)
        self.ansys.lesize("ALL", self.test_case.mesh.elementSpacing)
        self.ansys.mshkey(1)
        self.ansys.vmesh("ALL")

    def get_retained_nodes(self):
        coord_indices = [
            [(0, 0), (1, 0), (2, 0)],
            [(0, 1), (1, 0), (2, 0)],
            [(0, 0), (1, 1), (2, 0)],
            [(0, 0), (1, 0), (2, 1)],
        ]

        extents = self.mesh_extents()
        node_coords = [[extents[index] for index in node] for node in coord_indices]

        self.retained_nodes = []

        for node in node_coords:
            self.retained_nodes.append(self.get_node_num_at_loc(*node))

        return self.retained_nodes  # for logging purposes

    def get_node_num_at_loc(self, x, y, z):
        # WARNING: This uses the Ansys inline node() function, which returns whichever
        # node is CLOSEST to the location.
        inline = f"node({x},{y},{z})"
        self.ansys.run("NODE_NUMBER_TEMP=" + inline)
        return int(self.ansys.parameters["node_number_temp"])

    def select_node_at_loc(self, x, y, z, kind="S"):
        nnum = self.get_node_num_at_loc(x, y, z)
        if kind:
            self.ansys.nsel(kind, "NODE", "", nnum)

    def define_materials(self):
        self.ansys.run("/PREP7")
        e_str = ["EX", "EY", "EZ"]
        g_str = ["GXY", "GYZ", "GXZ"]
        pr_str = ["PRXY", "PRYZ", "PRXZ"]
        for material in self.test_case.materials:
            id = material.materialIndex
            for i in range(3):
                self.ansys.mp(e_str[i], id, material.elasticModuli[i])
                self.ansys.mp(g_str[i], id, material.shearModuli[i])
                self.ansys.mp(pr_str[i], id, material.poissonsRatios[i])
        # How do I verify that materials were input correctly? How do I access the
        # materials from self.ansys?

    def assign_element_materials(self):
        # This implementation is probably super slow
        # Individual emodif commands may be extra slow, so try adding to component
        # per material number, then emodif on each component
        self.ansys.run("/PREP7")
        for element in self.test_case.mesh.locationsWithId:
            self.ansys.esel("S", "CENT", "X", element[0])
            self.ansys.esel("R", "CENT", "Y", element[1])
            self.ansys.esel("R", "CENT", "Z", element[2])
            self.ansys.emodif("ALL", "MAT", element[3])

        self.ansys.allsel()

    def apply_loading_normal(self, axis):
        for j, n in enumerate(self.retained_nodes):
            for axis_label in NORMAL_FIXED_AXES[j]:
                self.ansys.d(n, axis_label)

        self.ansys.d(
            self.retained_nodes[axis],
            "U" + AXES[axis - 1],
            self.test_case.loading.normalMagnitude,
        )

    def apply_loading_shear(self, axis):
        for j, n in enumerate(self.retained_nodes):
            for axis_label in SHEAR_FIXED_AXES[j]:
                self.ansys.d(n, axis_label)

        self.ansys.d(
            self.retained_nodes[axis],
            "U" + AXES[axis % 3],
            self.test_case.loading.shearMagnitude,
        )

        # How do I verify that load steps were input correctly? How do I access the
        # load steps from self.ansys?

    def solve(self):
        with self.ansys.non_interactive:
            self.ansys.run("/SOLU")
            self.ansys.allsel()
            self.ansys.solve()

    def extract_raw_results(self):
        result = self.ansys.result
        coord = result.mesh.nodes
        nnum, disp = result.nodal_displacement(0)
        _, force = result.nodal_static_forces(0)

        self.retained_results = []
        for n in self.retained_nodes:
            n_results = {}
            n_idx = np.argwhere(nnum == n)[0, 0]
            n_results["coord"] = coord[n_idx]
            n_results["disp"] = disp[n_idx]
            n_results["force"] = force[n_idx]
            self.retained_results.append(n_results)

        pass

    def calculate_properties(self):
        ret_res = self.retained_results

        vol = self.ansys.mesh.grid.volume
        macro_stress = (
            reduce(
                lambda x, y: x + y,
                [np.outer(ret_res[i]["coord"], ret_res[i]["force"]) for i in range(4)],
            )
            / vol
        )

        rel_coord = [ret_res[i]["coord"] - ret_res[0]["coord"] for i in range(4)]
        macro_strain_true = reduce(  # I know it's not "true" strain. Can't remember what this should be called
            lambda x, y: x + y,
            [
                nonfinite_to_zero(np.outer(ret_res[n]["disp"], 1.0 / rel_coord[n]))
                for n in range(1, 4)
            ],
        )
        macro_strain = 0.5 * (macro_strain_true + np.transpose(macro_strain_true))


        properties = {}
        properties["elasticModuli"] = [
            macro_stress[i, i] / macro_strain[i, i] for i in range(3)
        ]
        properties["poissonsRatios"] = [
            -1.0 * macro_strain[i, i] / macro_strain[j, j]
            for i, j in permutations(range(3), r=2)
        ]
        properties["shearModuli"] = [
            macro_stress[i, j] / macro_strain[i, j]
            for i, j in permutations(range(3), r=2)
        ]

        self.test_case.results.append(properties)

    def load_parameters(self):
        try:
            self.ansys.load_parameters()
            self.parameters = self.ansys.parameters
        except:
            raise Exception("Unable to load Ansys parameters")

    def mesh_extents(self, current=False):
        if not current:
            return np.reshape(self.ansys.mesh.grid.bounds, (-1, 2))
        else:
            mins = self.ansys.mesh.nodes.min(axis=0)
            maxs = self.ansys.mesh.nodes.max(axis=0)
            return np.column_stack((mins, maxs))

    def debug_stat(self):
        self.ansys.lsoper()
        self.ansys.stat()
        self.ansys.fecons()
        self.ansys.stat()
        self.ansys.ceqn()
        self.ansys.stat()
